from diagrams import Cluster, Diagram, Edge
from diagrams.alibabacloud.application import OpenSearch
from diagrams.aws.compute import ECS
from diagrams.aws.database import Aurora
from diagrams.aws.general import Users
from diagrams.aws.integration import SimpleNotificationServiceSnsTopic
from diagrams.aws.management import (
    AutoScaling,
    Cloudwatch,
    CloudwatchAlarm,
    ParameterStore,
)
from diagrams.aws.network import ELB
from diagrams.aws.security import WAF
from diagrams.aws.storage import S3
from diagrams.gcp.devtools import ContainerRegistry

graph_attr = {
    "fontsize": "14",
    "bgcolor": "transparent",
    "splines": "ortho",
}

with Diagram(
    "AWS architecture",
    filename="aws_architecture",
    outformat="jpg",
    direction="TB",
    show=False,
    graph_attr=graph_attr,
):
    with Cluster("I.AI dev account"):  # noqa: SIM117
        with Cluster("eu-west-2"):
            with Cluster("VPC"):
                with Cluster("Keycloak"):
                    keycloak = ECS("Keycloak")

                with Cluster("Vector store"):
                    opensearch = OpenSearch("Opensearch")

                with Cluster("Image repo"):
                    ecr = ContainerRegistry("ECR")

                with Cluster("Private subnet") as private_subnet:
                    waf = WAF("WAF")

                    with Cluster("SNS"):
                        sns_topic = SimpleNotificationServiceSnsTopic("SNS")

                    with Cluster("ECS"):
                        frontend = ECS("Admin site")
                        backend = ECS("Backend & MCP Server")

                    with Cluster("Autoscaling"):
                        usage_scaling_group = AutoScaling("Usage scaling")
                        peaktime_scaling_group = AutoScaling("Peak time scaling")

                    with Cluster("Observability"):
                        cloudwatch_alarms = CloudwatchAlarm("Service monitoring")

                    with Cluster("File storage"):
                        s3 = S3("AWS S3 bucket")

                    with Cluster("Secret storage"):
                        ssm = ParameterStore("AWS parameter store")

                    with Cluster("App logs/metrics"):
                        cloudwatch = Cloudwatch("CloudWatch logs")

                    with Cluster("Persistent storage"):
                        rds = Aurora("Aurora postgresql")

                with Cluster("Public subnet"):
                    alb = ELB("Application load balancer")

    users = Users("User")

    users >> alb

    alb >> keycloak >> alb

    alb >> waf >> backend
    backend >> s3
    backend >> ssm
    backend >> cloudwatch

    backend >> Edge() << rds

    ecr >> backend
    ecr >> frontend

    backend >> sns_topic
    usage_scaling_group >> backend
    peaktime_scaling_group >> backend
    cloudwatch_alarms >> backend

    backend >> Edge() << opensearch

    alb >> waf >> frontend
    frontend >> s3
    frontend >> ssm
    frontend >> cloudwatch
    usage_scaling_group >> frontend
    peaktime_scaling_group >> frontend
    cloudwatch_alarms >> frontend

    frontend >> Edge() << backend
