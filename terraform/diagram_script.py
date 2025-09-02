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
from diagrams.aws.network import ELB, Route53
from diagrams.aws.security import WAF
from diagrams.aws.storage import S3
from diagrams.azure.ml import AzureOpenAI
from diagrams.aws.ml import Bedrock
from diagrams.gcp.devtools import ContainerRegistry
from diagrams.generic.blank import Blank

graph_attr = {
    "fontsize": "14",
    "bgcolor": "transparent",
    "splines": "ortho",
    "beautify": "true",
    "esep": "+6",
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
        route_53 = Route53("Route53")
        gov_waf = WAF("WAF")
        caddy_waf = WAF("WAF")

        with Cluster("eu-west-2"):
            with Cluster("VPC"):
                with Cluster("Keycloak"):
                    keycloak = ECS("Keycloak")

                with Cluster("Vector store"):
                    opensearch = OpenSearch("Opensearch")

                with Cluster("Image repo"):
                    ecr = ContainerRegistry("ECR")

                with Cluster(
                    "LLM gateway private subnet"
                ) as llm_gateway_private_subnet:
                    with Cluster("ECS"):
                        llm_gateway_ecs = ECS("LLM gateway")

                with Cluster("Gov-ai-client private subnet") as gov_ai_private_subnet:
                    with Cluster("SNS"):
                        gov_sns_topic = SimpleNotificationServiceSnsTopic("SNS")

                    with Cluster("ECS"):
                        gov_frontend = ECS("Gov AI client")

                    with Cluster("Autoscaling"):
                        gov_usage_scaling_group = AutoScaling("Usage scaling")
                        gov_peaktime_scaling_group = AutoScaling("Peak time scaling")

                    with Cluster("Observability"):
                        gov_cloudwatch_alarms = CloudwatchAlarm("Service monitoring")

                    with Cluster("Secret storage"):
                        gov_ssm = ParameterStore("AWS parameter store")

                    with Cluster("App logs/metrics"):
                        gov_cloudwatch = Cloudwatch("CloudWatch logs")

                with Cluster("GovAI public subnet"):
                    gov_alb = ELB("Application load balancer")

                with Cluster("Caddy private subnet") as caddy_private_subnet:
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

                with Cluster("Caddy public subnet"):
                    alb = ELB("Application load balancer")

    with Cluster("External LLM providers"):
        with Cluster("OpenAI"):
            oa = AzureOpenAI("OpenAI")
        with Cluster("Gemini"):
            gemini = Blank("Gemini")
        with Cluster("Bedrock"):
            bedrock = Bedrock("Bedrock")

    with Cluster("External MCP tools"):
        with Cluster("GovUK Acronyms"):
            acronyms = Blank("Acronyms")
        with Cluster("GovUK Search"):
            search = Blank("Search")
        with Cluster("Other LLM"):
            mcp_other = Blank("Other")

    users = Users("User")

    users >> route_53

    route_53 >> gov_waf
    route_53 >> caddy_waf

    caddy_waf >> alb

    gov_waf >> gov_alb

    llm_gateway_ecs >> oa
    llm_gateway_ecs >> gemini
    llm_gateway_ecs >> bedrock

    gov_frontend >> acronyms
    gov_frontend >> search
    gov_frontend >> mcp_other

    alb >> Edge() << keycloak

    gov_alb >> Edge() << keycloak

    gov_frontend >> llm_gateway_ecs

    gov_alb >> gov_frontend
    gov_frontend - gov_ssm
    gov_frontend >> gov_cloudwatch
    gov_frontend >> gov_sns_topic
    gov_usage_scaling_group >> gov_frontend
    gov_peaktime_scaling_group >> gov_frontend
    gov_cloudwatch_alarms >> gov_frontend

    alb >> backend
    backend >> Edge() << s3
    backend - ssm
    backend >> cloudwatch

    backend >> Edge() << rds

    ecr >> backend
    ecr >> frontend
    ecr >> gov_frontend

    backend >> sns_topic
    usage_scaling_group >> backend
    peaktime_scaling_group >> backend
    cloudwatch_alarms >> backend

    backend >> Edge() << opensearch

    alb >> frontend
    frontend - ssm
    frontend >> cloudwatch
    usage_scaling_group >> frontend
    peaktime_scaling_group >> frontend
    cloudwatch_alarms >> frontend

    frontend >> Edge() << backend
