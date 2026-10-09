#!/usr/bin/env python3
from aws_cdk import core
from bucket_policy_stack import BucketPolicyStack

app = core.App()

# Deploy the stack
BucketPolicyStack(app, "cdk")

app.synth()
