# Inspect S3 text files

`inspect_s3.py` paginates through all objects under a configurable bucket/prefix,
selects `.txt` files (case-insensitive extension), decodes strict UTF-8, and prints
the full filename/key, whitespace-separated word count and first 200 characters.
Preview strings escape newlines. Each response body is closed after reading.
Individual read failures do not prevent processing other files. Exit code is 1
for failures, 0 for success (including no matches). No objects are modified.

## Local AWS access

Install AWS CLI v2 if `aws --version` is unavailable. If your organization uses
IAM Identity Center, configure and log into a named profile:

```powershell
aws configure sso --profile rag-dev
aws sso login --profile rag-dev
$env:AWS_PROFILE = 'rag-dev'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
aws sts get-caller-identity
```

Your administrator supplies the SSO start URL, account, and role. The SSO portal
region can differ from the bucket region; the S3 client region is Sydney.
If you use IAM access keys instead, run `aws configure --profile rag-dev` and
enter keys at the prompts. Temporary credentials also require a session token.
Never use root account keys or put credentials in code or shell arguments.

AWS profiles live in your user-home `.aws` directory, outside the project.
Boto3 uses AWS's standard credential chain, including environment variables,
shared profiles and runtime roles. Stale environment credentials can override
profile credentials: remove them when switching to SSO. No credentials are
passed to boto3 in the script.

## Install and run from the project root

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:S3_BUCKET_NAME = 'your-bucket-name'
$env:S3_PREFIX = 'documents/'
& .\.venv\Scripts\python.exe injection/inspect_s3.py
```

Or supply arguments:

```powershell
& .\.venv\Scripts\python.exe injection/inspect_s3.py --bucket your-bucket-name --prefix documents/ --region ap-southeast-2
```

Use an empty prefix for bucket-root files. Prefixes are literal and
case-sensitive. Supply the bucket name without `s3://`. The script discovers
all matching text files, including hr_onboarding.txt, finance_payroll.txt and
it_helpdesk.txt when present under that prefix.

The script reads process environment variables; it does not automatically load
`.env`. `.env.example` documents configuration names. `.gitignore` excludes
local `.env` files, `.aws/`, and `.venv/`. Never commit populated credentials.
`requirements.txt` adds only boto3; its version range is not a lockfile.

## Permissions and failures

Your identity needs `s3:ListBucket` on `arn:aws:s3:::YOUR_BUCKET` and
`s3:GetObject` on `arn:aws:s3:::YOUR_BUCKET/YOUR_PREFIX*`. Prefix-restricted
policies must allow the exact prefix used for listing. SSE-KMS objects may
also require `kms:Decrypt` and authorization in the KMS key policy.
Bucket policies and explicit denies can override IAM allows.

AccessDenied errors explain these requirements. Verify the active identity with
`aws sts get-caller-identity` and ask your AWS administrator to grant access.
For expired SSO credentials, rerun `aws sso login --profile rag-dev`.
Invalid UTF-8 files are reported and skipped. Each entire file is read into
memory, appropriate for small text documents. Previews contain document content;
keep terminal output private. This step stops before chunking or embeddings.


