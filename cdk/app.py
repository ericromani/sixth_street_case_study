#!/usr/bin/env python3
from aws_cdk import App
from s3_lambda_vpc_stack import S3LambdaVpcStack

app = App()

S3LambdaVpcStack(app, "S3LambdaVpcStack")

app.synth()
