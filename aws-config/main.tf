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

  # REDIS sentinel bus
  ingress {
    description = "Redis Sentinel Bus"
    from_port   = 26379
    to_port     = 26379
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.custom_vpc.cidr_block] # Restrict to VPC internal traffic
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
######################################## RABBITMQ CLUSTER ########################################
# 1 EC2 instance for main RabbitMQ server
resource "aws_instance" "rabbitmq_primary" {
  count                  = 1
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_rabbit_mq_node
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]

  # Prefab key of labs
  key_name               = "vockey"

  user_data = templatefile("rabbitmq_setup.tftpl", {
    grafana_user_id = var.grafana_username,
    grafana_api_key = var.grafana_api_key
  })

  tags = {
    Name = "task1-RabbitMQ-Primary-Node"
    Role = "MessageBroker"
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
    primary_ip = aws_instance.rabbitmq_primary[0].private_ip,
    grafana_user_id = var.grafana_username,
    grafana_api_key = var.grafana_api_key
  })

  tags = {
    Name = "task1-RabbitMQ-Secondary-Node-${count.index + 1}"
    Role = "MessageBroker"
  }
}
##################################################################################################

######################################## REDIS CLUSTER ########################################
# Secondary nodes instances
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

resource "aws_instance" "redis_secondary" {
  count                  = 2
  ami                    = var.ec2_ami_id
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.custom_subnet.id
  vpc_security_group_ids = [aws_security_group.custom_sg.id]
  key_name               = "vockey"

  user_data = templatefile("redis_secondary_setup.tftpl", {
    primary_ip = aws_instance.redis_primary[0].private_ip
  })

  tags = {
    Name = "task1-Redis-Secondary-${count.index + 1}"
    Role = "RedisCluster"
  }
}
###############################################################################################


################################ ELASTIC LOAD BALANCING ################################
# NLB to connect the workers to the different RabbitMQ nodes
resource "aws_lb" "rabbitmq_nlb" {
  name               = "task1-rabbitmq-nlb"
  internal           = true
  load_balancer_type = "network"

  # The subnets where your NLB will be provisioned
  subnets            = [aws_subnet.custom_subnet.id]

  tags = {
    Name = "RabbitMQ-NLB"
  }
}

# Target group for AWS NLB (i.e. RabbitMQ instances).
resource "aws_lb_target_group" "rabbitmq_tg" {
  name     = "rabbitmq-tcp-tg"
  port     = 5672
  protocol = "TCP"
  vpc_id   = aws_vpc.custom_vpc.id

  # Health check configuration to ensure traffic is only sent to alive nodes
  health_check {
    protocol            = "TCP"
    port                = "5672"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    interval            = 10
  }
}

# Listener to receive AMQP traffic and route it to the instances available in the target group.
resource "aws_lb_listener" "rabbitmq_listener" {
  load_balancer_arn = aws_lb.rabbitmq_nlb.arn
  port              = "5672"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.rabbitmq_tg.arn
  }
}

# Attach Primary Node(s)
# The depends_on ensures attachments happen only after EC2 instances exist
resource "aws_lb_target_group_attachment" "rabbitmq_primary_attachment" {
  count            = length(aws_instance.rabbitmq_primary)
  target_group_arn = aws_lb_target_group.rabbitmq_tg.arn
  target_id        = aws_instance.rabbitmq_primary[count.index].id
  port             = 5672

  depends_on       = [aws_instance.rabbitmq_primary]
}

# Attach Secondary Node(s)
resource "aws_lb_target_group_attachment" "rabbitmq_secondary_attachment" {
  count            = length(aws_instance.rabbitmq_nodes)
  target_group_arn = aws_lb_target_group.rabbitmq_tg.arn
  target_id        = aws_instance.rabbitmq_nodes[count.index].id
  port             = 5672

  depends_on       = [aws_instance.rabbitmq_nodes]
}
########################################################################################

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
  depends_on = [aws_lb_listener.rabbitmq_listener, aws_instance.redis_primary, aws_instance.rabbitmq_nodes, aws_instance.redis_secondary]

  user_data = templatefile("worker_setup.tftpl", {
    rabbitmq_host = aws_lb.rabbitmq_nlb.dns_name,
    redis_sentinels = join(",", concat([aws_instance.redis_primary[0].private_ip], aws_instance.redis_secondary[*].private_ip))
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