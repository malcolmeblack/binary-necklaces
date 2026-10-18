#!/usr/bin/env python3
"""Build and deploy the chatbot without replacing the shared website resources.

AWS credentials use the ordinary boto3 provider chain (including AWS_PROFILE).
Only ./deploy.sh runs this program; importing it has no side effects.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import zipfile

def _require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set.")
    return value

ACCOUNT = _require_env("CHATBOT_ACCOUNT")
REGION = os.environ.get("CHATBOT_REGION", "us-west-2")
DISTRIBUTION = _require_env("CHATBOT_DISTRIBUTION")
REST_API = _require_env("CHATBOT_REST_API")
PUBLIC_BUCKET = _require_env("CHATBOT_PUBLIC_BUCKET")
PRIVATE_BUCKET = _require_env("CHATBOT_PRIVATE_BUCKET")
PREFIX = "binary-necklaces/chatbot/"
API_DOMAIN = f"{REST_API}.execute-api.{REGION}.amazonaws.com"
API_ORIGIN = "binary-necklaces-chatbot-rest-api"
STATIC_ORIGIN = "binary-necklaces-chatbot-static"
STACK = "binary-necklaces-chatbot-shared"
API_FUNCTION = "binary-necklaces-chatbot-api"
CACHE_DISABLED = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
ALL_VIEWER_EXCEPT_HOST = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".deploy"


class DeploymentError(RuntimeError):
    pass


def error_code(exc):
    return getattr(exc, "response", {}).get("Error", {}).get("Code", "")


def items(value):
    return value.get("Items", []) if value else []


def resolve_stage(config, stages, explicit=None):
    """Prefer the existing BNCT origin's stage; never invent a stage name."""
    names = {stage["stageName"] for stage in stages}
    if explicit:
        if explicit not in names:
            raise DeploymentError(f"REST API stage {explicit!r} does not exist.")
        return explicit
    origins = {origin["Id"]: origin for origin in items(config.get("Origins"))}
    behaviors = items(config.get("CacheBehaviors")) + [config.get("DefaultCacheBehavior", {})]
    matching = []
    for behavior in behaviors:
        pattern = behavior.get("PathPattern", "*").lstrip("/")
        if fnmatch.fnmatchcase("api/bnct/calc", pattern):
            matching.append(behavior)
            break  # CloudFront uses the first match.
    candidates = set()
    for behavior in matching:
        origin = origins.get(behavior.get("TargetOriginId"), {})
        if origin.get("DomainName") == API_DOMAIN:
            stage = origin.get("OriginPath", "").strip("/")
            if stage in names:
                candidates.add(stage)
    if len(candidates) == 1:
        return candidates.pop()
    if len(names) == 1:
        return names.pop()
    raise DeploymentError("Cannot identify the existing REST API stage. Run ./deploy.sh --stage NAME "
                          "with one of: " + ", ".join(sorted(names)))


def validate_shared_distribution(config):
    # Error pages apply distribution-wide, including API responses. Do not change
    # the whole site's error handling or let it turn JSON errors into HTML.
    remapped = [str(rule["ErrorCode"]) for rule in items(config.get("CustomErrorResponses"))
                if rule.get("ResponsePagePath") or rule.get("ResponseCode")]
    if remapped:
        raise DeploymentError("The existing CloudFront distribution remaps error responses (" +
                              ", ".join(remapped) + "). These global rules would replace chatbot JSON "
                              "errors. Review those rules before deployment; this script leaves them unchanged.")
    if not config.get("Enabled", True):
        raise DeploymentError("The existing CloudFront distribution is disabled.")


def merge_lifecycle(rules):
    result = copy.deepcopy(rules)
    rule_id = "binary-necklaces-chatbot-job-expiration"
    rule = {"ID": rule_id, "Status": "Enabled", "Filter": {"Prefix": PREFIX + "jobs/"},
            "Expiration": {"Days": 30}, "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}}
    for index, old in enumerate(result):
        if old.get("ID") == rule_id:
            if old.get("Filter", {}).get("Prefix", old.get("Prefix")) != PREFIX + "jobs/":
                raise DeploymentError("The chatbot lifecycle rule ID is already used for another prefix.")
            result[index] = rule
            break
    else:
        if len(result) >= 1000:
            raise DeploymentError("The private bucket has no free lifecycle rule slot.")
        result.append(rule)
    return result


def _collection(values):
    return {"Quantity": len(values), **({"Items": values} if values else {})}


def _is_bucket_origin(origin):
    domain = origin.get("DomainName", "")
    return (not origin.get("OriginPath") and
            (domain == PUBLIC_BUCKET + ".s3.amazonaws.com" or
             re.fullmatch(re.escape(PUBLIC_BUCKET) + r"\.s3[.-][a-z0-9-]+\.amazonaws\.com", domain)))


def merge_cloudfront(config, api_domain, stage, secret, function_arn, static_cache_policy_id,
                     public_region=REGION):
    """Add four specific behaviors ahead of broader rules; retain unrelated state."""
    result = copy.deepcopy(config)
    origins = items(result.get("Origins"))
    existing_static = next((origin for origin in origins if _is_bucket_origin(origin)
                            and origin["Id"] != API_ORIGIN), None)
    static_id = existing_static["Id"] if existing_static else STATIC_ORIGIN
    api_origin = {
        "Id": API_ORIGIN, "DomainName": api_domain, "OriginPath": "/" + stage,
        "CustomHeaders": _collection([{"HeaderName": "x-api-origin", "HeaderValue": secret}]),
        "CustomOriginConfig": {"HTTPPort": 80, "HTTPSPort": 443,
                               "OriginProtocolPolicy": "https-only",
                               "OriginSslProtocols": _collection(["TLSv1.2"]),
                               "OriginReadTimeout": 30, "OriginKeepaliveTimeout": 5},
        "ConnectionAttempts": 2, "ConnectionTimeout": 5,
    }
    for origin in origins:
        if origin["Id"] == API_ORIGIN and origin.get("DomainName") != api_domain:
            raise DeploymentError("The reserved chatbot API origin ID is already used by another origin.")
        if origin["Id"] == STATIC_ORIGIN and not _is_bucket_origin(origin):
            raise DeploymentError("The reserved chatbot static origin ID is already used by another origin.")
    if any(origin["Id"] == API_ORIGIN for origin in origins):
        origins = [api_origin if origin["Id"] == API_ORIGIN else origin for origin in origins]
    else:
        origins.append(api_origin)
    if not existing_static:
        origins.append({"Id": static_id,
                        "DomainName": f"{PUBLIC_BUCKET}.s3.{public_region}.amazonaws.com",
                        "OriginPath": "", "S3OriginConfig": {"OriginAccessIdentity": ""},
                        "ConnectionAttempts": 3, "ConnectionTimeout": 10})
    result["Origins"] = _collection(origins)
    common = {"ViewerProtocolPolicy": "redirect-to-https", "Compress": True,
              "SmoothStreaming": False,
              "TrustedSigners": {"Enabled": False, "Quantity": 0},
              "TrustedKeyGroups": {"Enabled": False, "Quantity": 0},
              "LambdaFunctionAssociations": {"Quantity": 0},
              "FieldLevelEncryptionId": ""}
    api = {**common, "TargetOriginId": API_ORIGIN,
           "AllowedMethods": {"Quantity": 7, "Items": ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
                              "CachedMethods": _collection(["GET", "HEAD"])},
           "CachePolicyId": CACHE_DISABLED, "OriginRequestPolicyId": ALL_VIEWER_EXCEPT_HOST,
           "FunctionAssociations": {"Quantity": 0}}
    static = {**common, "TargetOriginId": static_id,
              "AllowedMethods": {**_collection(["GET", "HEAD"]),
                                 "CachedMethods": _collection(["GET", "HEAD"])},
              "CachePolicyId": static_cache_policy_id,
              "FunctionAssociations": _collection([{"EventType": "viewer-request", "FunctionARN": function_arn}])}
    paths = ["/api/chatbot", "/api/chatbot/*", "/" + PREFIX.rstrip("/"), "/" + PREFIX + "*"]
    # Do not repurpose a reserved origin if an unrelated behavior already uses it.
    for behavior in items(config.get("CacheBehaviors")) + [config.get("DefaultCacheBehavior", {})]:
        if behavior.get("TargetOriginId") in (API_ORIGIN, STATIC_ORIGIN) and \
                behavior.get("PathPattern", "").lstrip("/") not in {path.lstrip("/") for path in paths}:
            raise DeploymentError("A reserved chatbot origin is in use by an unrelated CloudFront behavior.")
    retained = [behavior for behavior in items(result.get("CacheBehaviors"))
                if behavior.get("PathPattern", "").lstrip("/") not in {path.lstrip("/") for path in paths}]
    added = [{**copy.deepcopy(api if index < 2 else static), "PathPattern": path}
             for index, path in enumerate(paths)]
    result["CacheBehaviors"] = _collection(added + retained)
    return result


def stage_patches():
    patches = []
    for path, method, rate, burst in (("/api/chatbot", "POST", "1", "2"),
                                      ("/api/chatbot/{jobId}", "GET", "20", "40")):
        key = path.replace("~", "~0").replace("/", "~1") + "/" + method
        for setting, value in (("caching/enabled", "false"), ("logging/dataTrace", "false"),
                               ("throttling/rateLimit", rate), ("throttling/burstLimit", burst)):
            patches.append({"op": "replace", "path": "/" + key + "/" + setting, "value": value})
    return patches


def save_backup(name, data):
    path = STATE / "backups" / name
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    path.chmod(0o600)


def get_stack(cf):
    try:
        return cf.describe_stacks(StackName=STACK)["Stacks"][0]
    except Exception as exc:
        if error_code(exc) == "ValidationError" and "does not exist" in str(exc):
            return None
        raise


def validate_existing_stack(cf, stack):
    if not stack:
        return
    required = {"ApiFunction", "WorkerFunction", "ApiRole", "WorkerRole", "ChatbotIndex", "StaticCachePolicy"}
    allowed_types = {"AWS::Lambda::Function", "AWS::Lambda::Permission", "AWS::Lambda::EventInvokeConfig",
                     "AWS::IAM::Role", "AWS::Logs::LogGroup", "AWS::CloudFront::Function", "AWS::CloudFront::CachePolicy",
                     "AWS::ApiGateway::Resource", "AWS::ApiGateway::Method",
                     "AWS::CloudWatch::Alarm"}
    resources = []
    for page in cf.get_paginator("list_stack_resources").paginate(StackName=STACK):
        resources.extend(page.get("StackResourceSummaries", []))
    if not required.issubset({item["LogicalResourceId"] for item in resources}) or any(
            item["ResourceType"] not in allowed_types for item in resources):
        raise DeploymentError(f"Existing stack {STACK} is not the shared-resource chatbot stack. "
                              "It will not be replaced or migrated automatically.")


def stack_outputs(stack):
    return {item["OutputKey"]: item["OutputValue"] for item in (stack or {}).get("Outputs", [])}


def validate_function_names(lamb, stack):
    outputs = stack_outputs(stack)
    for name, key in ((API_FUNCTION, "ApiFunctionName"),
                      ("binary-necklaces-chatbot-worker", "WorkerFunctionName")):
        try:
            lamb.get_function_configuration(FunctionName=name)
        except Exception as exc:
            if error_code(exc) == "ResourceNotFoundException":
                continue
            raise
        if outputs.get(key) != name:
            raise DeploymentError(f"Lambda function {name} already exists outside this deployment stack. "
                                  "It will not be adopted or overwritten automatically.")


def get_origin_secret(lamb, old_stack, config):
    function_name = stack_outputs(old_stack).get("ApiFunctionName", API_FUNCTION)
    try:
        env = lamb.get_function_configuration(FunctionName=function_name).get("Environment", {}).get("Variables", {})
        secret = env.get("ORIGIN_SECRET", "")
        if secret:
            return secret
    except Exception as exc:
        if error_code(exc) != "ResourceNotFoundException":
            raise
    for origin in items(config.get("Origins")):
        if origin["Id"] == API_ORIGIN:
            for header in items(origin.get("CustomHeaders")):
                if header["HeaderName"].lower() == "x-api-origin":
                    return header["HeaderValue"]
    return secrets.token_hex(32)


def preflight(session, explicit_stage):
    if session.client("sts").get_caller_identity()["Account"] != ACCOUNT:
        raise DeploymentError(f"Use AWS credentials for account {ACCOUNT}.")
    api = session.client("apigateway")
    api_info = api.get_rest_api(restApiId=REST_API)
    if api_info.get("disableExecuteApiEndpoint"):
        raise DeploymentError("The REST API's execute-api endpoint is disabled; the dedicated CloudFront origin requires it.")
    cloudfront = session.client("cloudfront")
    snapshot = cloudfront.get_distribution_config(Id=DISTRIBUTION)
    validate_shared_distribution(snapshot["DistributionConfig"])
    stages = api.get_stages(restApiId=REST_API).get("item", [])
    stage = resolve_stage(snapshot["DistributionConfig"], stages, explicit_stage)
    stage_info = api.get_stage(restApiId=REST_API, stageName=stage)
    if stage_info.get("canarySettings", {}).get("percentTraffic", 0):
        raise DeploymentError("The shared REST API stage has active canary traffic. Resolve it before deploying chatbot routes.")
    s3 = session.client("s3")
    regions = {}
    for bucket in (PUBLIC_BUCKET, PRIVATE_BUCKET):
        s3.head_bucket(Bucket=bucket, ExpectedBucketOwner=ACCOUNT)
        regions[bucket] = s3.get_bucket_location(Bucket=bucket, ExpectedBucketOwner=ACCOUNT).get("LocationConstraint") or "us-east-1"
    if regions[PRIVATE_BUCKET] != REGION:
        raise DeploymentError(f"The private artifact bucket must be in {REGION} for this Lambda stack; found {regions[PRIVATE_BUCKET]}.")
    try:
        status = s3.get_bucket_policy_status(Bucket=PRIVATE_BUCKET, ExpectedBucketOwner=ACCOUNT)
        if status.get("PolicyStatus", {}).get("IsPublic"):
            raise DeploymentError("The private bucket policy currently permits public access.")
    except Exception as exc:
        if error_code(exc) != "NoSuchBucketPolicy":
            raise
    blocks = {}
    try:
        blocks.update(s3.get_public_access_block(Bucket=PRIVATE_BUCKET, ExpectedBucketOwner=ACCOUNT)["PublicAccessBlockConfiguration"])
    except Exception as exc:
        if error_code(exc) != "NoSuchPublicAccessBlockConfiguration":
            raise
    if not all(blocks.get(key) for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
        try:
            account_blocks = session.client("s3control").get_public_access_block(AccountId=ACCOUNT)["PublicAccessBlockConfiguration"]
            blocks = {key: value or account_blocks.get(key, False) for key, value in {
                "BlockPublicAcls": blocks.get("BlockPublicAcls", False),
                "IgnorePublicAcls": blocks.get("IgnorePublicAcls", False),
                "BlockPublicPolicy": blocks.get("BlockPublicPolicy", False),
                "RestrictPublicBuckets": blocks.get("RestrictPublicBuckets", False)}.items()}
        except Exception as exc:
            if error_code(exc) != "NoSuchPublicAccessBlockConfiguration":
                raise
    if not all(blocks.get(key) for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
        raise DeploymentError("Enable all four S3 Block Public Access settings on private bucket malcolmblack before deployment. No bucket policy is changed by this script.")
    try:
        lifecycle = s3.get_bucket_lifecycle_configuration(Bucket=PRIVATE_BUCKET, ExpectedBucketOwner=ACCOUNT)
        merge_lifecycle(lifecycle.get("Rules", []))
    except Exception as exc:
        if error_code(exc) != "NoSuchLifecycleConfiguration":
            raise
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    save_backup(f"{stamp}-cloudfront.json", snapshot)
    save_backup(f"{stamp}-rest-stage.json", stage_info)
    return stage, regions[PUBLIC_BUCKET]


def build():
    print("Building frontend and Lambda package...", flush=True)
    env = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1"}
    subprocess.run(["npm", "ci"], cwd=ROOT / "frontend", check=True, env=env)
    shutil.rmtree(ROOT / "frontend" / "out", ignore_errors=True)
    subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", check=True, env=env)
    if not (ROOT / "frontend" / "out" / "index.html").is_file():
        raise DeploymentError("The frontend build did not produce out/index.html.")
    package = STATE / "package"
    shutil.rmtree(package, ignore_errors=True)
    package.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--quiet", "--no-compile", "--target", str(package),
                    "-r", str(ROOT / "backend" / "lambda" / "requirements.txt")], check=True)
    shutil.copytree(ROOT / "backend" / "lambda", package, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "requirements.txt"))
    target = STATE / "lambda.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                info = zipfile.ZipInfo(path.relative_to(package).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    return target


def wait_for_stack(cf):
    # Polling also prints progress during deployments that take several minutes.
    last = None
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        stack = get_stack(cf)
        status = stack["StackStatus"] if stack else "DELETED"
        if status != last:
            print("CloudFormation: " + status, flush=True)
            last = status
        if status in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
            return stack
        if not status.endswith("IN_PROGRESS"):
            raise DeploymentError(f"CloudFormation ended with {status}. Review stack {STACK} events before retrying.")
        time.sleep(5)
    raise DeploymentError(f"CloudFormation is still running. Wait for stack {STACK} before deploying again.")


def get_api_parent_resource_id(api):
    """Look up the resource ID of /api in the existing REST API."""
    for page in api.get_paginator("get_resources").paginate(restApiId=REST_API):
        for item in page.get("items", []):
            if item["path"] == "/api":
                return item["id"]
    raise DeploymentError("The REST API has no /api resource.")


def deploy_stack(cf, package_key, secret, old_stack, calculator_arn, api_parent_id):
    parameters = {"OriginSecret": secret, "CodeBucket": PRIVATE_BUCKET, "CodeKey": package_key,
                  "PrivateBucketName": PRIVATE_BUCKET, "PrivatePrefix": PREFIX.rstrip("/"),
                  "RestApiId": REST_API, "ApiParentResourceId": api_parent_id}
    if calculator_arn is not None:
        parameters["CalculatorFunctionArn"] = calculator_arn
    alarm_topic = os.environ.get("CHATBOT_ALARM_TOPIC_ARN", "")
    if alarm_topic:
        parameters["AlarmTopicArn"] = alarm_topic
    encoded = [{"ParameterKey": key, "ParameterValue": value} for key, value in parameters.items()]
    # Parameters whose template defaults change across versions should not
    # keep their previous values. Let the updated template defaults apply.
    use_template_default = {"ModelId", "FoundationModelId", "UseInferenceProfile", "AlarmTopicArn"}
    if old_stack:
        encoded += [{"ParameterKey": item["ParameterKey"], "UsePreviousValue": True}
                    for item in old_stack.get("Parameters", [])
                    if item["ParameterKey"] not in parameters and item["ParameterKey"] not in use_template_default]
    request = {"StackName": STACK, "TemplateBody": (ROOT / "backend" / "template.yaml").read_text(),
               "Parameters": encoded, "Capabilities": ["CAPABILITY_NAMED_IAM"]}
    if old_stack:
        if old_stack["StackStatus"].endswith("IN_PROGRESS"):
            raise DeploymentError("The chatbot CloudFormation stack is already changing; wait before deploying again.")
        try:
            cf.update_stack(**request)
        except Exception as exc:
            if error_code(exc) == "ValidationError" and "No updates are to be performed" in str(exc):
                return old_stack
            raise
    else:
        cf.create_stack(**request, EnableTerminationProtection=True,
                        Tags=[{"Key": "Application", "Value": "binary-necklaces-chatbot"}])
    return wait_for_stack(cf)


def deploy_api(api, stage):
    # The template creates the API Gateway resources and methods. This step
    # applies per-method stage settings and publishes the deployment.
    api.update_stage(restApiId=REST_API, stageName=stage, patchOperations=stage_patches())
    print(f"Publishing REST API stage {stage}. This includes all currently pending changes on that REST API.", flush=True)
    return api.create_deployment(restApiId=REST_API, stageName=stage,
                                 description="Binary necklaces chatbot deployment")["id"]


def deploy_lifecycle(s3):
    options = {}
    try:
        current = s3.get_bucket_lifecycle_configuration(Bucket=PRIVATE_BUCKET, ExpectedBucketOwner=ACCOUNT)
        rules = current.get("Rules", [])
        if "TransitionDefaultMinimumObjectSize" in current:
            options["TransitionDefaultMinimumObjectSize"] = current["TransitionDefaultMinimumObjectSize"]
    except Exception as exc:
        if error_code(exc) != "NoSuchLifecycleConfiguration":
            raise
        current, rules = {}, []
    merged = merge_lifecycle(rules)
    if merged != rules:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        save_backup(f"{stamp}-private-lifecycle.json", current)
        s3.put_bucket_lifecycle_configuration(Bucket=PRIVATE_BUCKET, ExpectedBucketOwner=ACCOUNT,
                                              LifecycleConfiguration={"Rules": merged}, **options)


def upload_frontend(s3):
    source = ROOT / "frontend" / "out"
    paths = sorted((path for path in source.rglob("*") if path.is_file()),
                   key=lambda path: (path.suffix == ".html", path.as_posix()))
    for path in paths:
        relative = path.relative_to(source).as_posix()
        immutable = relative.startswith("_next/static/")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix in (".js", ".mjs"):
            content_type = "application/javascript"
        if path.suffix == ".css":
            content_type = "text/css"
        s3.upload_file(str(path), PUBLIC_BUCKET, PREFIX + relative,
                       ExtraArgs={"ContentType": content_type,
                                  "CacheControl": "public,max-age=31536000,immutable" if immutable else "no-cache",
                                  "ExpectedBucketOwner": ACCOUNT})
    # Keep older hashed chunks so in-flight page loads survive an update.


def deploy_distribution(cloudfront, stage, secret, outputs, public_region):
    # Fetch a fresh ETag after uploads. A simultaneous distribution edit will fail
    # the conditional update instead of silently overwriting someone else's work.
    snapshot = cloudfront.get_distribution_config(Id=DISTRIBUTION)
    config = snapshot["DistributionConfig"]
    validate_shared_distribution(config)
    merged = merge_cloudfront(config, API_DOMAIN, stage, secret,
                             outputs["IndexFunctionArn"], outputs["StaticCachePolicyId"], public_region)
    if merged != config:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        save_backup(f"{stamp}-cloudfront-before-update.json", snapshot)
        cloudfront.update_distribution(Id=DISTRIBUTION, IfMatch=snapshot["ETag"], DistributionConfig=merged)
    invalidation = cloudfront.create_invalidation(DistributionId=DISTRIBUTION, InvalidationBatch={
        "CallerReference": "chatbot-" + secrets.token_hex(12),
        "Paths": _collection(["/" + PREFIX.rstrip("/"), "/" + PREFIX + "*", "/api/chatbot*"])})
    return invalidation["Invalidation"]["Id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", help="existing REST API stage; otherwise detected from BNCT's CloudFront origin")
    parser.add_argument("--profile", help="AWS shared configuration profile")
    parser.add_argument("--calculator-function-arn", help="optional existing BNCT Lambda ARN for direct invocation")
    args = parser.parse_args()
    os.umask(0o077)
    STATE.mkdir(exist_ok=True, mode=0o700)
    import boto3
    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    stage, public_region = preflight(session, args.stage)
    print(f"Using existing account {ACCOUNT}, REST API {REST_API} stage {stage}, and CloudFront {DISTRIBUTION}.", flush=True)
    cf = session.client("cloudformation")
    old_stack = get_stack(cf)
    validate_existing_stack(cf, old_stack)
    validate_function_names(session.client("lambda"), old_stack)
    snapshot = session.client("cloudfront").get_distribution_config(Id=DISTRIBUTION)
    secret = get_origin_secret(session.client("lambda"), old_stack, snapshot["DistributionConfig"])
    # Structural validation before any AWS writes; actual output IDs arrive after
    # the stack update. This also catches a reserved origin-name collision early.
    merge_cloudfront(snapshot["DistributionConfig"], API_DOMAIN, stage, secret,
                     "preflight-function", "preflight-policy", public_region)
    package = build()
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    package_key = PREFIX + "artifacts/" + digest + ".zip"
    s3 = session.client("s3")
    s3.upload_file(str(package), PRIVATE_BUCKET, package_key,
                   ExtraArgs={"ContentType": "application/zip", "ServerSideEncryption": "AES256",
                              "ExpectedBucketOwner": ACCOUNT})
    api_parent_id = get_api_parent_resource_id(session.client("apigateway"))
    stack = deploy_stack(cf, package_key, secret, old_stack, args.calculator_function_arn, api_parent_id)
    outputs = stack_outputs(stack)
    deploy_lifecycle(s3)
    deployment = deploy_api(session.client("apigateway"), stage)
    upload_frontend(s3)
    invalidation = deploy_distribution(session.client("cloudfront"), stage, secret, outputs, public_region)
    receipt = {"stack": STACK, "stage": stage, "apiDeploymentId": deployment,
               "cloudFrontInvalidationId": invalidation, "artifactKey": package_key,
               "url": "https://malcolmblack.org/binary-necklaces/chatbot/"}
    (STATE / "last-deployment.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Deployment submitted. CloudFront propagation and cache invalidation may take several minutes.")
    print(receipt["url"])


if __name__ == "__main__":
    try:
        main()
    except (DeploymentError, subprocess.CalledProcessError) as exc:
        print("Deployment stopped: " + str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # Do not dump request objects or environment variables: they include the
        # origin secret. AWS service error messages usually identify missing IAM.
        code = error_code(exc)
        print(f"Deployment stopped: {type(exc).__name__}" + (f" ({code})" if code else "") +
              ". Review AWS permissions and the service's deployment events.", file=sys.stderr)
        sys.exit(1)
