<img width="1472" height="863" alt="sixthStreet" src="https://github.com/user-attachments/assets/7068242a-e9c1-4d9a-942a-73c49784f0d4" />

### Deploy
The lambda is built using a Github Action, but we need to run update-function-code on the lambda passing in the new artifact to update it. This can be done in the action but actions won't give us much control or orchestration. Tying build and deploy too tightly will give us too little control. For deploy we would want a unique pipeline that allows us to update the function with a version we pass in at runtime. This can be chained in the build workflow to deploy released by default in a test environment but still give us control over deploying to a production environment. We would want to auto deploy to a test environment, then once that is tested, it can be promoted to a prod environment. Having a deploy pipeline will allow this and also allow rollbacks if necessary. 

### Stack separation
I've put all the infra in a single stack for simplicity but generally I would have separate stacks here. Likely for this scenario I would have at least 2. One for the "base resources" (vpc, subnets, vpc endpoint, artifacts bucket) anything that is likely to be shared. Then another for the actual app in question (lambda, lambda iam role, sg, source and dest buckets, dlq, trigger). 

### Repo separation 
To keep workflows clean, I would put the lambda code and build in its own repo, so it can have checks that are relevant to it. Code scanning for quality and needed version bumps. Lambda build and publish, tagging the repo to keep the repo tags in line with published versions of the artifact. CDK would live elsewhere in a repo intended for that in which the infrastructure deploy workflow would be wired up. 

### Assumptions
- Assuming custom Github runner in AWS env that has IAM role allowing it to push to the artifacts bucket. 
- Assuming a single AWS region deploy

### Other things to add in a real world case
- Alerting on the DLQ
- Exporting Lambda Logs
- Custom metrics published from the Lambda - alerting
- VPC with egress filtering and internet egress
- Bucket lifecycle policy to remove old unused artifacts
- Testing environment - deploy to test, verify with metrics, deploy to prod.
