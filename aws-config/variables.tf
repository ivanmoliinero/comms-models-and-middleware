variable "aws_region" {
  type        = string
  description = "The AWS region to deploy into"
  default     = "us-east-1"
}

variable "vpc_cidr_block" {
  type        = string
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/24"
}

variable "subnet_cidr_block" {
  type        = string
  description = "CIDR block for the Subnet"
  default     = "10.0.0.0/24"
}

# WARNING: The value displayed here changes between regions.
variable "ec2_ami_id" {
  type        = string
  description = "The exact AMI ID for the EC2 instances"
  default     = "ami-01b14b7ad41e17ba4" # Amazon Linux 2023 kernel-6.1
}

variable "ec2_instance_type" {
  type        = string
  description = "The EC2 instance type (e.g., t2.micro, t3.small)"
  default     = "t3.micro"
}

# The RabbitMQ nodes will have more resources than client or worker nodes who rely totally on them.
variable "ec2_rabbit_mq_node" {
  type        = string
  description = "The EC2 instance type for RabbitMQ servers."
  default     = "t3.small"
}

# The Redis nodes will have more resources than client or worker nodes who rely totally on them.
variable "ec2_redis_node" {
  type        = string
  description = "The EC2 instance type for RabbitMQ servers."
  default     = "t3.small"
}