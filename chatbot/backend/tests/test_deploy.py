"""Offline checks for scoped updates to the website's shared AWS resources."""
import copy
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "deploy.py"

# Provide test values for the required env vars so deploy.py can be imported.
_TEST_ENV = {
    "CHATBOT_ACCOUNT": "000000000000",
    "CHATBOT_DISTRIBUTION": "EXXXXXXXXTEST",
    "CHATBOT_REST_API": "testapi123",
    "CHATBOT_PUBLIC_BUCKET": "test-public-bucket",
    "CHATBOT_PRIVATE_BUCKET": "test-private-bucket",
}
for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)

spec = importlib.util.spec_from_file_location("chatbot_deploy", MODULE_PATH)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def existing_distribution():
    """A live site with an existing BNCT route and broad API fallback."""
    return {
        "CallerReference": "existing-website",
        "Aliases": {"Quantity": 1, "Items": [deploy.PUBLIC_BUCKET]},
        "Comment": "Main website",
        "Enabled": True,
        "DefaultRootObject": "index.html",
        "Origins": {"Quantity": 2, "Items": [
            {"Id": "website", "DomainName": f"{deploy.PUBLIC_BUCKET}.s3.{deploy.REGION}.amazonaws.com",
             "OriginPath": "", "S3OriginConfig": {"OriginAccessIdentity": ""}},
            {"Id": "existing-api", "DomainName": deploy.API_DOMAIN,
             "OriginPath": "/prod", "CustomOriginConfig": {
                 "HTTPPort": 80, "HTTPSPort": 443, "OriginProtocolPolicy": "https-only",
                 "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]}}},
        ]},
        "DefaultCacheBehavior": {
            "TargetOriginId": "website", "ViewerProtocolPolicy": "redirect-to-https",
            "CachePolicyId": "original-site-policy", "Compress": True,
            "TrustedSigners": {"Enabled": False, "Quantity": 0},
            "TrustedKeyGroups": {"Enabled": False, "Quantity": 0},
        },
        "CacheBehaviors": {"Quantity": 3, "Items": [
            {"PathPattern": "/api/bnct/*", "TargetOriginId": "existing-api",
             "ViewerProtocolPolicy": "https-only", "CachePolicyId": "bnct-policy"},
            {"PathPattern": "/api/*", "TargetOriginId": "existing-api",
             "ViewerProtocolPolicy": "https-only", "CachePolicyId": "api-policy"},
            {"PathPattern": "/binary-necklaces/*", "TargetOriginId": "website",
             "ViewerProtocolPolicy": "redirect-to-https", "CachePolicyId": "necklaces-policy"},
        ]},
        "CustomErrorResponses": {"Quantity": 0},
        "ViewerCertificate": {"ACMCertificateArn": "arn:aws:acm:us-east-1:000000000000:certificate/existing",
                              "SSLSupportMethod": "sni-only", "MinimumProtocolVersion": "TLSv1.2_2021"},
        "Logging": {"Enabled": False, "IncludeCookies": False, "Bucket": "", "Prefix": ""},
        "HttpVersion": "http2and3",
        "IsIPV6Enabled": True,
        "WebACLId": "existing-web-acl",
    }


class StageSelectionTests(unittest.TestCase):
    def test_uses_existing_bnct_stage_when_api_has_multiple_stages(self):
        self.assertEqual(deploy.resolve_stage(existing_distribution(),
            [{"stageName": "prod"}, {"stageName": "dev"}]), "prod")

    def test_explicit_stage_must_already_exist(self):
        stages = [{"stageName": "prod"}, {"stageName": "dev"}]
        self.assertEqual(deploy.resolve_stage(existing_distribution(), stages, "dev"), "dev")
        with self.assertRaises(deploy.DeploymentError):
            deploy.resolve_stage(existing_distribution(), stages, "missing")

    def test_sole_stage_fallback_without_matching_api_origin(self):
        config = existing_distribution()
        config["Origins"]["Items"][1]["DomainName"] = "unrelated.example.com"
        self.assertEqual(deploy.resolve_stage(config, [{"stageName": "production"}]), "production")
        with self.assertRaises(deploy.DeploymentError):
            deploy.resolve_stage(config, [{"stageName": "prod"}, {"stageName": "dev"}])

    def test_cloudfront_first_match_wins_over_shadowed_bnct_route(self):
        config = existing_distribution()
        dev_origin = copy.deepcopy(config["Origins"]["Items"][1])
        dev_origin.update(Id="development-api", OriginPath="/dev")
        config["Origins"]["Items"].append(dev_origin)
        config["Origins"]["Quantity"] += 1
        config["CacheBehaviors"]["Items"].insert(0,
            {"PathPattern": "api/*", "TargetOriginId": "development-api"})
        config["CacheBehaviors"]["Quantity"] += 1
        self.assertEqual(deploy.resolve_stage(config,
            [{"stageName": "prod"}, {"stageName": "dev"}]), "dev")

    def test_does_not_guess_when_stage_path_is_not_recognized(self):
        config = existing_distribution()
        config["Origins"]["Items"][1]["OriginPath"] = "/prod/api"
        with self.assertRaises(deploy.DeploymentError):
            deploy.resolve_stage(config, [{"stageName": "prod"}, {"stageName": "dev"}])
        with self.assertRaises(deploy.DeploymentError):
            deploy.resolve_stage(config, [])


class LifecycleTests(unittest.TestCase):
    def test_preserves_unrelated_rules_and_expires_only_job_prefix(self):
        rules = [{"ID": "website-logs", "Status": "Enabled", "Filter": {"Prefix": "logs/"},
                  "Expiration": {"Days": 90}}]
        original = copy.deepcopy(rules)
        updated = deploy.merge_lifecycle(rules)
        self.assertEqual(rules, original)
        self.assertEqual(updated[0], original[0])
        jobs = updated[1]
        self.assertEqual(jobs["Filter"], {"Prefix": "binary-necklaces/chatbot/jobs/"})
        self.assertEqual(jobs["Status"], "Enabled")
        self.assertEqual(jobs["Expiration"], {"Days": 30})
        self.assertEqual(jobs["NoncurrentVersionExpiration"], {"NoncurrentDays": 30})
        self.assertEqual(deploy.merge_lifecycle(updated), updated)

    def test_rejects_same_rule_id_owned_by_another_prefix(self):
        existing = deploy.merge_lifecycle([])
        existing[0]["Filter"]["Prefix"] = "unrelated/"
        with self.assertRaises(deploy.DeploymentError):
            deploy.merge_lifecycle(existing)

    def test_bucket_rule_limit_does_not_remove_other_rules(self):
        rules = [{"ID": str(i), "Status": "Enabled", "Filter": {"Prefix": f"other/{i}/"},
                  "Expiration": {"Days": 90}} for i in range(1000)]
        with self.assertRaises(deploy.DeploymentError):
            deploy.merge_lifecycle(rules)
        self.assertEqual(len(rules), 1000)


class CloudFrontTests(unittest.TestCase):
    def merge(self, config):
        return deploy.merge_cloudfront(config,
            deploy.API_DOMAIN, "prod", "test-secret",
            f"arn:aws:cloudfront::{deploy.ACCOUNT}:function/chatbot-index", "chatbot-static-policy")

    def test_specific_paths_precede_broad_fallbacks_and_preserve_website(self):
        config = existing_distribution()
        original = copy.deepcopy(config)
        updated = self.merge(config)
        self.assertEqual(config, original)
        old_behaviors = original["CacheBehaviors"]["Items"]
        new_behaviors = updated["CacheBehaviors"]["Items"]
        self.assertEqual([item["PathPattern"] for item in new_behaviors[:4]],
            ["/api/chatbot", "/api/chatbot/*", "/binary-necklaces/chatbot", "/binary-necklaces/chatbot/*"])
        self.assertEqual(new_behaviors[4:], old_behaviors)
        for key in original.keys() - {"Origins", "CacheBehaviors"}:
            self.assertEqual(updated[key], original[key], key)
        self.assertEqual(updated["Origins"]["Items"][:2], original["Origins"]["Items"])
        self.assertEqual(updated["Origins"]["Quantity"], len(updated["Origins"]["Items"]))
        self.assertEqual(updated["CacheBehaviors"]["Quantity"], len(new_behaviors))

    def test_api_forwards_authorization_without_caching_or_viewer_host(self):
        updated = self.merge(existing_distribution())
        for behavior in updated["CacheBehaviors"]["Items"][:2]:
            self.assertEqual(behavior["CachePolicyId"], "4135ea2d-6df8-44a3-9df3-4b5a84be39ad")
            self.assertEqual(behavior["OriginRequestPolicyId"], "b689b0a8-53d0-40ab-baf2-68738e2966ac")
            self.assertIn("POST", behavior["AllowedMethods"]["Items"])
            self.assertIn("GET", behavior["AllowedMethods"]["Items"])
            self.assertEqual(behavior["FunctionAssociations"]["Quantity"], 0)
        origin = next(origin for origin in updated["Origins"]["Items"]
                      if origin["Id"] == updated["CacheBehaviors"]["Items"][0]["TargetOriginId"])
        self.assertEqual(origin["OriginPath"], "/prod")
        self.assertEqual(origin["DomainName"], deploy.API_DOMAIN)
        self.assertEqual(origin["CustomHeaders"]["Items"],
            [{"HeaderName": "x-api-origin", "HeaderValue": "test-secret"}])

    def test_static_routes_reuse_public_origin_and_apply_index_function_only_there(self):
        updated = self.merge(existing_distribution())
        for behavior in updated["CacheBehaviors"]["Items"][2:4]:
            self.assertEqual(behavior["TargetOriginId"], "website")
            self.assertEqual(behavior["CachePolicyId"], "chatbot-static-policy")
            self.assertEqual(behavior["AllowedMethods"]["Items"], ["GET", "HEAD"])
            self.assertEqual(behavior["FunctionAssociations"]["Items"], [{
                "EventType": "viewer-request",
                "FunctionARN": f"arn:aws:cloudfront::{deploy.ACCOUNT}:function/chatbot-index"}])
        self.assertEqual(len(updated["Origins"]["Items"]), 3)

    def test_new_public_origin_uses_public_bucket_actual_region(self):
        config = existing_distribution()
        config["Origins"]["Items"][0]["DomainName"] = "old-site.example.com"
        updated = deploy.merge_cloudfront(config, deploy.API_DOMAIN, "prod", "secret",
            "function-arn", "cache-policy", public_region="us-east-1")
        new_static = next(item for item in updated["Origins"]["Items"]
                          if item["Id"] == deploy.STATIC_ORIGIN)
        self.assertEqual(new_static["DomainName"], f"{deploy.PUBLIC_BUCKET}.s3.us-east-1.amazonaws.com")
        self.assertEqual(new_static["OriginPath"], "")
        self.assertEqual(deploy.merge_cloudfront(updated, deploy.API_DOMAIN, "prod", "secret",
            "function-arn", "cache-policy", public_region="us-east-1"), updated)

    def test_redeployment_is_idempotent_and_normalizes_existing_paths(self):
        updated = self.merge(existing_distribution())
        self.assertEqual(self.merge(updated), updated)
        updated["CacheBehaviors"]["Items"][0]["PathPattern"] = "api/chatbot"
        self.assertEqual(len(self.merge(updated)["CacheBehaviors"]["Items"]), 7)

    def test_reserved_origin_collision_does_not_repurpose_other_application(self):
        config = existing_distribution()
        config["Origins"]["Items"].append({"Id": deploy.API_ORIGIN, "DomainName": "elsewhere.example.com"})
        config["Origins"]["Quantity"] += 1
        with self.assertRaises(deploy.DeploymentError):
            self.merge(config)
        config = self.merge(existing_distribution())
        config["DefaultCacheBehavior"]["TargetOriginId"] = deploy.API_ORIGIN
        with self.assertRaises(deploy.DeploymentError):
            self.merge(config)

    def test_global_error_page_remapping_is_rejected_without_mutation(self):
        config = existing_distribution()
        config["CustomErrorResponses"] = {"Quantity": 1, "Items": [
            {"ErrorCode": 403, "ResponseCode": "200", "ResponsePagePath": "/index.html",
             "ErrorCachingMinTTL": 0}]}
        original = copy.deepcopy(config)
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_shared_distribution(config)
        self.assertEqual(config, original)

    def test_zero_ttl_error_rules_and_enabled_distribution_are_allowed(self):
        config = existing_distribution()
        config["CustomErrorResponses"] = {"Quantity": 1, "Items": [
            {"ErrorCode": 403, "ErrorCachingMinTTL": 0}]}
        deploy.validate_shared_distribution(config)
        config["Enabled"] = False
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_shared_distribution(config)


class StagePatchTests(unittest.TestCase):
    def test_caching_logging_and_throttles_apply_only_to_chatbot_methods(self):
        patches = deploy.stage_patches()
        allowed = {"/~1api~1chatbot/POST/", "/~1api~1chatbot~1{jobId}/GET/"}
        self.assertEqual(len(patches), 8)
        for patch in patches:
            self.assertTrue(any(patch["path"].startswith(prefix) for prefix in allowed), patch)
            self.assertNotIn("*", patch["path"])
            if patch["path"].endswith(("caching/enabled", "logging/dataTrace")):
                self.assertEqual(patch["value"], "false")
        self.assertEqual(sum(patch["path"].endswith("caching/enabled") for patch in patches), 2)


class DeploymentOwnershipTests(unittest.TestCase):
    def test_existing_shared_resource_stack_can_be_updated(self):
        cf = Mock()
        resources = [
            {"LogicalResourceId": "ApiFunction", "ResourceType": "AWS::Lambda::Function"},
            {"LogicalResourceId": "WorkerFunction", "ResourceType": "AWS::Lambda::Function"},
            {"LogicalResourceId": "ApiRole", "ResourceType": "AWS::IAM::Role"},
            {"LogicalResourceId": "WorkerRole", "ResourceType": "AWS::IAM::Role"},
            {"LogicalResourceId": "ChatbotIndex", "ResourceType": "AWS::CloudFront::Function"},
            {"LogicalResourceId": "StaticCachePolicy", "ResourceType": "AWS::CloudFront::CachePolicy"},
            {"LogicalResourceId": "ChatbotApiResource", "ResourceType": "AWS::ApiGateway::Resource"},
            {"LogicalResourceId": "ChatbotJobApiResource", "ResourceType": "AWS::ApiGateway::Resource"},
            {"LogicalResourceId": "ChatbotPostMethod", "ResourceType": "AWS::ApiGateway::Method"},
            {"LogicalResourceId": "ChatbotGetMethod", "ResourceType": "AWS::ApiGateway::Method"},
        ]
        cf.get_paginator.return_value.paginate.return_value = [
            {"StackResourceSummaries": resources[:3]}, {"StackResourceSummaries": resources[3:]}]
        deploy.validate_existing_stack(cf, {"StackName": deploy.STACK})
        cf.get_paginator.assert_called_once_with("list_stack_resources")
        cf.update_stack.assert_not_called()

    def test_old_standalone_stack_is_not_adopted_or_replaced(self):
        cf = Mock()
        cf.get_paginator.return_value.paginate.return_value = [{"StackResourceSummaries": [
            {"LogicalResourceId": "ApiFunction", "ResourceType": "AWS::Lambda::Function"},
            {"LogicalResourceId": "WebsiteBucket", "ResourceType": "AWS::S3::Bucket"},
            {"LogicalResourceId": "Distribution", "ResourceType": "AWS::CloudFront::Distribution"},
        ]}]
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_existing_stack(cf, {"StackName": deploy.STACK})
        cf.update_stack.assert_not_called()
        cf.delete_stack.assert_not_called()

    def test_existing_function_names_require_ownership_outputs(self):
        lamb = Mock()
        lamb.get_function_configuration.return_value = {"Runtime": "python3.12"}
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_function_names(lamb, None)
        stack = {"Outputs": [
            {"OutputKey": "ApiFunctionName", "OutputValue": deploy.API_FUNCTION},
            {"OutputKey": "WorkerFunctionName", "OutputValue": "binary-necklaces-chatbot-worker"},
        ]}
        deploy.validate_function_names(lamb, stack)
        absent = RuntimeError("absent")
        absent.response = {"Error": {"Code": "ResourceNotFoundException"}}
        lamb.get_function_configuration.side_effect = absent
        deploy.validate_function_names(lamb, None)
        lamb.update_function_code.assert_not_called()
        lamb.delete_function.assert_not_called()


if __name__ == "__main__":
    unittest.main()
