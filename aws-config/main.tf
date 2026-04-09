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

  availability_zone = "us-east-1a"
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

  # RabbitMQ AMQP port for clients and workers
  # WARNING: Due to limitations given by specs and AWS lab, clients will be outside the VPC.
  # TODO: Change to 5671 encrypted protocol + restrict permissions on clients.
  ingress {
    description = "AMQP protocol"
    from_port   = 5672
    to_port     = 5672
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # RabbitMQ Management UI
  ingress {
    description = "Management UI"
    from_port   = 15672
    to_port     = 15672
    protocol    = "tcp"
    # Currently open to the internet to allow browser access
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Erlang Port Mapper Daemon for cluster node discovery
  ingress {
    description = "Erlang Port Mapper Daemon"
    from_port   = 4369
    to_port     = 4369
    protocol    = "tcp"
    # Allows traffic only from within the VPC
    cidr_blocks = [aws_vpc.custom_vpc.cidr_block]
  }

  # RabbitMQ inter-node communication for clustering
  ingress {
    description = "RabbitMQ cluster communication"
    from_port   = 25672
    to_port     = 25672
    protocol    = "tcp"
    # Allows traffic only from within the VPC
    cidr_blocks = [aws_vpc.custom_vpc.cidr_block]
  }

  # HTTP internal comms to obtain state of RabbitMQ servers
  ingress {
    description = "Allow HTTP traffic on port 80 for Nginx cloud-init check"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.custom_vpc.cidr_block]
  }

  # REDIS internal comms
  ingress {
    description = "Allow HTTP traffic on port 80 for Nginx cloud-init check"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.custom_vpc.cidr_block]
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
# 1 EC2 instance for main RabbitMQ server
resource "aws_instance" "rabbitmq_primary" {
  count                  = 1
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_rabbit_mq_node
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]

  # Prefab key of labs
  key_name               = "vockey"

  user_data = templatefile("rabbitmq_setup.tftpl", {})

  tags = {
    Name = "task1-RabbitMQ-Primary-Node"
    Role = "MessageBroker"
  }
}

# 1 EC2 instance for main Redis server.
resource "aws_instance" "redis_primary" {
  count                  = 1
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_redis_node
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]

  # Prefab key of labs
  key_name               = "vockey"

  user_data = templatefile("redis_setup.tftpl", {})

  tags = {
    Name = "task1-Redis-Primary-Node"
    Role = "StateStore"
  }
}

# 2 EC2 Instances for RabbitMQ Cluster (Quorum Queue)
# (3 total instances)
resource "aws_instance" "rabbitmq_nodes" {
  count                  = 2
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_rabbit_mq_node
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]

  # Strictly wait for the primary node to be provisioned first
  depends_on = [aws_instance.rabbitmq_primary]

  # Prefab key of labs
  key_name               = "vockey"

  # They need private IP of main node in order to be setup.
  user_data = templatefile("rabbitmq_secondary_setup.tftpl", {
    primary_ip = aws_instance.rabbitmq_primary[0].private_ip
  })

  tags = {
    Name = "task1-RabbitMQ-Secondary-Node-${count.index + 1}"
    Role = "MessageBroker"
  }
}

# EC2 Instances for Workers
resource "aws_instance" "worker_nodes" {
  count                  = 3
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]

  # Prefab key of labs
  key_name               = "vockey"

  # Establish dependency on rabbitmq nodes in order to retrieve private IPs inside VPC for communication.
  depends_on = [aws_instance.rabbitmq_primary, aws_instance.redis_primary, aws_instance.rabbitmq_nodes]

  # The RabbitMQ accessed server will be the first one available for all.
  user_data = templatefile("worker_setup.tftpl", {
    rabbitmq_host = count.index % 3 == 0 ? aws_instance.rabbitmq_primary[0].private_ip : aws_instance.rabbitmq_nodes[(count.index % 3) - 1].private_ip,
    redis_host = aws_instance.redis_primary[0].private_ip,
    shard = count.index % 3
  })

  tags = {
    Name = "task1-Worker-Node-${count.index + 1}"
    Role = "Worker"
  }
}

# # 1 EC2 Instance for Publisher Clients
# resource "aws_instance" "publisher_nodes" {
#   count                  = 1
#   ami                    = var.ec2_ami_id
#   instance_type          = var.ec2_instance_type
#   subnet_id              = aws_subnet.custom_subnet.id
#   vpc_security_group_ids = [aws_security_group.custom_sg.id]
#
#   # Prefab key of labs
#   key_name               = "vockey"
#
#   # Establish dependency on rabbitmq nodes in order to retrieve private IPs inside VPC for communication.
#   depends_on = [aws_instance.rabbitmq_primary]
#
#   user_data = templatefile("client_setup.tftpl", {
#     rabbitmq_host = aws_instance.rabbitmq_primary[0].private_ip
#   })
#
#   tags = {
#     Name = "task1-Publisher-Client-${count.index + 1}"
#     Role = "Publisher"
#   }
# }

# Output the Public IPs for the RabbitMQ Management UI
output "rabbitmq_main_node_management_url" {
  value       = ["http://${aws_instance.rabbitmq_primary[0].public_ip}:15672"]
  description = "URLs to access the RabbitMQ Management UI from your browser"
}