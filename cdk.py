from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_sqs as sqs,
    aws_ec2 as ec2,
    aws_s3_notifications as s3n,
    RemovalPolicy,
    Duration
)
from constructs import Construct


class S3LambdaVpcStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -----------------------
        # 1. VPC with 3 private subnets
        # -----------------------
        vpc = ec2.Vpc(
            self, "LambdaVpc",
            max_azs=3,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PrivateSubnet",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ]
        )

        # -----------------------
        # 2. S3 Gateway Endpoint
        # -----------------------
        vpc.add_gateway_endpoint(
            "S3GatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3
        )

        # -----------------------
        # 3. Security Group for Lambda
        # -----------------------
        lambda_sg = ec2.SecurityGroup(
            self, "LambdaSG",
            vpc=vpc,
            description="Allow Lambda egress to S3 endpoint on 443",
            allow_all_outbound=False
        )
        lambda_sg.add_egress_rule(
            peer=ec2.Peer.prefix_list(s3_prefix_list_id),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS to S3 endpoint"
        )

        # -----------------------
        # 4. Lambda Execution Role
        # -----------------------
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )

        # -----------------------
        # 5. Buckets
        # -----------------------
        # Map of bucket configurations
        bucket_configs = {
            "SourceBucket": {
                "actions": ["s3:GetObject"]
            },
            "ArtifactsBucket": {
                "actions": ["s3:GetObject"]
            },
            "DestinationBucket": {
                "actions": ["s3:PutObject"]
            }
        }

        # Dictionary to store bucket objects
        self.buckets = {}

        for bucket_name, config in bucket_configs.items():
            # Create bucket
            bucket = s3.Bucket(
                self, bucket_name,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True,
                encryption=s3.BucketEncryption.S3_MANAGED
            )

            # Attach bucket policy for Lambda role
            bucket.add_to_resource_policy(
                iam.PolicyStatement(
                    sid=f"{bucket_name}AccessForLambda",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ArnPrincipal(lambda_role.role_arn)],
                    actions=config["actions"],
                    resources=[f"{bucket.bucket_arn}/*"]
                )
            )

            self.buckets[bucket_name] = bucket

        # Optional: Output bucket names
        for name, bucket in self.buckets.items():
            core.CfnOutput(self, f"{name}Name", value=bucket.bucket_name)


        # -----------------------
        # 6. Lambda IAM Permissions
        # -----------------------
        # Source bucket: Get + List
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject", "s3:ListBucket"],
            resources=[
                buckets["SourceBucket"].bucket_arn,
                f"{buckets['SourceBucket'].bucket_arn}/*"
            ]
        ))

        # Artifacts bucket: Get + List
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject", "s3:ListBucket"],
            resources=[
                buckets["ArtifactsBucket"].bucket_arn,
                f"{buckets['ArtifactsBucket'].bucket_arn}/*"
            ]
        ))

        # Destination bucket: Put + PutObjectAcl
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:PutObject", "s3:PutObjectAcl"],
            resources=[f"{buckets['DestinationBucket'].bucket_arn}/*"]
        ))

        # -----------------------
        # 7. Artifacts Bucket Policy (Allow Read to Whole Account) - This or the bucket policy above giving access just to the lambda role.
        # -----------------------
        account_id = "111122223333"  # Fake AWS Account ID
        buckets["ArtifactsBucket"].add_to_resource_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[iam.AccountPrincipal(account_id)],
            actions=["s3:GetObject"],
            resources=[f"{buckets['ArtifactsBucket'].bucket_arn}/*"]
        ))

        # -----------------------
        # 8. Dead Letter Queue
        # -----------------------
        dlq = sqs.Queue(
            self, "LambdaDLQ",
            retention_period=Duration.days(14)
        )

        # -----------------------
        # 9. Lambda Function
        # -----------------------
        lambda_function = _lambda.Function(
            self, "VpcLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_bucket(
                bucket=buckets["ArtifactsBucket"],
                key="lambda-code.zip"
            ),
            role=lambda_role,
            vpc=vpc,
            security_groups=[lambda_sg],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            dead_letter_queue=dlq,
            timeout=Duration.seconds(30),
            environment={
                "DEST_BUCKET": buckets["DestinationBucket"].bucket_name
            }
        )

        # -----------------------
        # 10. S3 Event Notification Trigger
        # -----------------------
        buckets["SourceBucket"].add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(lambda_function)
        )
