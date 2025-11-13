variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "phil-apps"
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "telegram_bot_token" {
  description = "Telegram Bot Token"
  type        = string
  sensitive   = true
}

variable "google_ai_api_key" {
  description = "Google AI API Key for Gemini"
  type        = string
  sensitive   = true
}
