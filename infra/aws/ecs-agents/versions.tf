terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Reads GITHUB_TOKEN from the environment; see "Spin down / spin up" in README.md.
provider "github" {
  owner = split("/", var.github_repository)[0]
}
