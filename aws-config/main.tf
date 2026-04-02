terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS Provider configuration
provider "aws" {
  region = var.aws_region
}

# VPC definition
resource "aws_vpc" "custom_vpc" {
  cidr_block           = var.vpc_cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "task1-vpc"
  }
}

# Internet Gateway definition
resource "aws_internet_gateway" "custom_igw" {
  vpc_id = aws_vpc.custom_vpc.id

  tags = {
    Name = "task1-igw"
  }
}

# Subnet definition
resource "aws_subnet" "custom_subnet" {
  vpc_id                  = aws_vpc.custom_vpc.id
  cidr_block              = var.subnet_cidr_block
  map_public_ip_on_launch = true

  tags = {
    Name = "task1-subnet"
  }
}

# Route Table definition
resource "aws_route_table" "custom_route_table" {
  vpc_id = aws_vpc.custom_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.custom_igw.id
  }

  tags = {
    Name = "task1-route-table"
  }
}

# Route Table Association
resource "aws_route_table_association" "custom_rta" {
  subnet_id      = aws_subnet.custom_subnet.id
  route_table_id = aws_route_table.custom_route_table.id
}

# Security Group definition
resource "aws_security_group" "custom_sg" {
  name        = "allow_basic_traffic"
  description = "Allow inbound traffic and all outbound traffic"
  vpc_id      = aws_vpc.custom_vpc.id

  ingress {
    description = "SSH from anywhere"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "task1-security-group"
  }
}

# EC2 Instance definition
# 3 EC2 Instances for RabbitMQ Cluster (Quorum Queue)
resource "aws_instance" "rabbitmq_nodes" {
  count                  = 3
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]

  tags = {
    Name = "task1-RabbitMQ-Node-${count.index + 1}"
    Role = "MessageBroker"
  }
}

# 2 EC2 Instances for Publisher Clients
resource "aws_instance" "publisher_nodes" {
  count                  = 2
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]

  tags = {
    Name = "task1-Publisher-Client-${count.index + 1}"
    Role = "Publisher"
  }
}

# 3 EC2 Instances for Workers
resource "aws_instance" "worker_nodes" {
  count                  = 3
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]

  tags = {
    Name = "task1-Worker-Node-${count.index + 1}"
    Role = "Worker"
  }
}