# Binary Necklace Chatbot

The chatbot answers questions about the binary necklaces exposition using Amazon Bedrock and the BNCT calculator. The interface retains its existing layout, fonts, colors, and progress messages.

## Architecture

The API returns a job ID and private bearer token immediately. The browser polls for progress while two First Responder → Skeptic → Arbiter sequences run in parallel, followed by a Judge. Generation runs independently of the REST API request timeout.

The deployment reuses the existing website's CloudFront distribution, REST API, and S3 buckets. CloudFormation manages the chatbot's Lambda functions, IAM roles, log groups, invocation permissions, and dedicated CloudFront index function and cache policy. Existing website resources are not imported into the stack.

## Files

| Path | Contents |
| --- | --- |
| `frontend/` | Interface source, tests, fonts, and ready-to-upload `out/` export |
| `backend/lambda/` | API handler, analysis worker, prompts, BNCT tool, and bundled reference |
| `backend/template.yaml` | CloudFormation definition for chatbot-specific resources |
| `backend/deploy.py` | Deployment implementation called by `deploy.sh` |
| `backend/tests/` | Offline backend and deployment tests |

Only `frontend/out/` is published to the public bucket. Backend code, reference material, and job records are never included in that upload.

## Deploy

Install Python 3.12 or newer with `venv` and `pip`, Node.js 20.9 or newer, and npm. Configure AWS credentials that can update the listed resources and create the chatbot's CloudFormation stack and IAM roles. The account must have access to the configured Bedrock model. AWS CLI and SAM CLI are not required by the deployment script.

Set the required environment variables (in `.deploy/env` or your shell profile):

```bash
export CHATBOT_ACCOUNT=...           # AWS account ID
export CHATBOT_DISTRIBUTION=...      # Existing CloudFront distribution ID
export CHATBOT_REST_API=...          # Existing API Gateway REST API ID
export CHATBOT_PUBLIC_BUCKET=...     # Public S3 bucket for the website
export CHATBOT_PRIVATE_BUCKET=...    # Private S3 bucket for jobs and artifacts
export CHATBOT_ALARM_TOPIC_ARN=...   # Optional SNS topic ARN for usage alarms
```

Then run from this directory:

```bash
./deploy.sh
```

Use the same command for subsequent updates. It builds the application, uploads the Lambda package to the private bucket, creates or updates the chatbot stack, configures the chatbot resources on the existing REST API, updates its deployment, publishes the static interface, and updates the chatbot's CloudFront routing.

The script uses the normal AWS credential chain, including `AWS_PROFILE`; an explicit profile can be selected with `./deploy.sh --profile PROFILE`. The optional `--calculator-function-arn ARN` connects directly to an existing BNCT calculator Lambda; otherwise the worker uses the deployed `/api/bnct/calc` URL.

The script discovers the REST API stage from the existing CloudFront API origin or, if there is only one, from the API's stages. If the stage is ambiguous, select it explicitly:

```bash
./deploy.sh --stage YOUR_EXISTING_STAGE
```

The existing `/api/bnct` resources and unrelated CloudFront origins and behaviors are preserved. API Gateway deploys a snapshot of the **whole REST API**, so complete or remove unrelated pending API edits before running a backend deployment.

The private bucket must have S3 Block Public Access enabled. Bucket policies and website-wide error-page rules are not replaced. If the existing CloudFront distribution replaces API errors with a custom HTML page, the script reports that conflict before deployment. New static assets are uploaded before the HTML; older hashed assets are retained so existing page loads can finish.

Local deployment state and configuration backups are kept under `.deploy/`, which is ignored by Git. The CloudFront origin secret stays in private deployment state and Lambda/CloudFront configuration; it is not embedded in the interface. Keep this directory private.

If a deployment stops, correct the reported issue and rerun the command. CloudFormation rollback covers its stack resources; REST API, CloudFront routing, and S3 updates are separate. The saved configuration backups support restoring those settings if needed.

CloudFront propagation and invalidation continue after the script submits the update. Wait for the distribution to finish deploying before the live check. The previous EC2 service can be retired after the new route is verified.

After deployment, open the chatbot in the exposition and submit a question. The network requests should use `/api/chatbot`; a POST returns `202`, followed by authenticated GET requests until the answer is ready. This is the live check of Bedrock access and website routing.

## Development

Backend checks do not invoke paid models:

```bash
python3 -m unittest discover -s backend/tests -v
```

Frontend development and checks:

```bash
cd frontend
npm ci
npm test
npm run dev
```

Open the development server at `/binary-necklaces/chatbot/`. For a static build, run `npm run build`; the clean export is written to `frontend/out/`.

Update `backend/lambda/knowledge/binary-necklaces.yml` when the exposition changes and redeploy. The calculator tool uses the current BNCT contract, preserves exact decimal-string counts, and distinguishes deferred values and partial previews from complete results.

Jobs are inaccessible after 15 minutes. A prefix-specific lifecycle rule expires their stored objects after 30 days; physical S3 deletion is asynchronous. Generation has a 225-second application budget within a 240-second Lambda invocation, with four concurrent workers by default. The application logs aggregate usage and safe error codes without recording questions, answers, or bearer tokens. Earlier displayed chat messages are not sent as conversation history, matching the previous service.
