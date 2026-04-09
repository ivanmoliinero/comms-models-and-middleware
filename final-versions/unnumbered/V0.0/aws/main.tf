# 1. PROVIDER CONFIGURATION
provider "aws" {
  region = "us-east-1"
}

# 2. NETWORK INFRASTRUCTURE
resource "aws_vpc" "redis_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "redis-cluster-vpc" }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.redis_vpc.id
  tags = { Name = "redis-cluster-igw" }
}

resource "aws_subnet" "main_subnet" {
  vpc_id                  = aws_vpc.redis_vpc.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true 
  availability_zone       = "us-east-1a"	# otherwise t3.micro cannot be find
  tags = { Name = "redis-cluster-subnet" }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.redis_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.main_subnet.id
  route_table_id = aws_route_table.public_rt.id
}

# 3. SECURITY GROUP (FIREWALL)
resource "aws_security_group" "redis_sg" {
  name        = "redis_cluster_sg"
  description = "Allow SSH, HTTP, and internal cluster traffic"
  vpc_id      = aws_vpc.redis_vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true 
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 4. DYNAMIC AMI DATA FETCH
# This queries AWS for the latest official Ubuntu 24.04 AMI in us-east-1
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Official Canonical AWS Account ID

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

variable "key_name" {
  default = "SD-task1-key-pair"
}

# 5. EC2 INSTANCES
resource "aws_instance" "control_plane" {
  count                  = 3
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.main_subnet.id
  vpc_security_group_ids = [aws_security_group.redis_sg.id]
  key_name               = var.key_name

  tags = {
    Name = "control-plane-node-${count.index + 1}"
    Role = "edge-and-sentinel"
  }
}

resource "aws_instance" "data_plane_masters" {
  count                  = 2
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.main_subnet.id
  vpc_security_group_ids = [aws_security_group.redis_sg.id]
  key_name               = var.key_name

  tags = {
    Name = "redis-master-${count.index == 0 ? "a" : "b"}"
    Role = "database-master"
  }
}

resource "aws_instance" "data_plane_replicas" {
  count                  = 4
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.main_subnet.id
  vpc_security_group_ids = [aws_security_group.redis_sg.id]
  key_name               = var.key_name

  tags = {
    Name = "redis-replica-${count.index < 2 ? "a" : "b"}${count.index % 2 + 1}"
    Role = "database-replica"
  }
}

# 6. OUTPUTS
output "control_plane_private_ips" {
  value = aws_instance.control_plane[*].private_ip
}

output "control_plane_public_ips" {
  value = aws_instance.control_plane[*].public_ip
}

output "master_private_ips" {
  value = aws_instance.data_plane_masters[*].private_ip
}

output "replica_private_ips" {
  value = aws_instance.data_plane_replicas[*].private_ip
}
