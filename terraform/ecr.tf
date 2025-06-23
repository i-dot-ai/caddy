
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

resource "aws_ecrpublic_repository" "public_caddy_model" {
  count = var.env == "dev" ? 1 : 0
  provider = aws.us_east_1

  repository_name = "caddy-model"

  catalog_data {
    about_text = "This is the Caddy Model Image"
    architectures = [
    "x86-64"]
    description = "Caddy Model Image"
    operating_systems = [
    "Linux"]
    usage_text = "-"
  }
}

resource "aws_ecrpublic_repository" "public_caddy_scraper" {
  count = var.env == "dev" ? 1 : 0
  provider = aws.us_east_1

  repository_name = "caddy-scraper"

  catalog_data {
    about_text = "This is the Caddy Scraper Image"
    architectures = [
    "x86-64"]
    description = "Caddy Scraper Image"
    operating_systems = [
    "Linux"]
    usage_text = "-"
  }
}

resource "aws_ecrpublic_repository" "public_caddy_frontend" {
  count = var.env == "dev" ? 1 : 0
  provider = aws.us_east_1

  repository_name = "caddy-frontend"

  catalog_data {
    about_text = "This is the Caddy Frontend Image"
    architectures = [
    "x86-64"]
    description = "Caddy Frontend Image"
    operating_systems = [
    "Linux"]
    usage_text = "-"
  }
}

resource "aws_ecrpublic_repository" "public_caddy_backend" {
  count = var.env == "dev" ? 1 : 0
  provider = aws.us_east_1

  repository_name = "caddy-backend"

  catalog_data {
    about_text = "This is the Caddy Backend Image"
    architectures = [
    "x86-64"]
    description = "Caddy Backend Image"
    operating_systems = [
    "Linux"]
    usage_text = "-"
  }
}