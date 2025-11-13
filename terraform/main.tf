terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "cloudfunctions" {
  service            = "cloudfunctions.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudbuild" {
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

# Create GCS bucket for Cloud Function source code
resource "google_storage_bucket" "function_bucket" {
  name                        = "${var.project_id}-telegram-bot-functions"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  depends_on = [google_project_service.cloudfunctions]
}

# Create secrets in Secret Manager
resource "google_secret_manager_secret" "telegram_bot_token" {
  secret_id = "telegram-bot-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "google_ai_api_key" {
  secret_id = "google-ai-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

# Secret versions (you'll need to populate these manually or via terraform.tfvars)
resource "google_secret_manager_secret_version" "telegram_bot_token_version" {
  secret      = google_secret_manager_secret.telegram_bot_token.id
  secret_data = var.telegram_bot_token
}

resource "google_secret_manager_secret_version" "google_ai_api_key_version" {
  secret      = google_secret_manager_secret.google_ai_api_key.id
  secret_data = var.google_ai_api_key
}

# Create a service account for the Cloud Function
resource "google_service_account" "function_sa" {
  account_id   = "telegram-transcribe-bot-sa"
  display_name = "Telegram Transcribe Bot Service Account"
}

# Grant the service account access to secrets
resource "google_secret_manager_secret_iam_member" "bot_token_access" {
  secret_id = google_secret_manager_secret.telegram_bot_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "api_key_access" {
  secret_id = google_secret_manager_secret.google_ai_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.function_sa.email}"
}

# Archive the source code
data "archive_file" "function_source" {
  type        = "zip"
  source_dir  = "${path.module}/../function_source"
  output_path = "${path.module}/function-source.zip"
}

# Upload source code to GCS
resource "google_storage_bucket_object" "function_source" {
  name   = "function-source-${data.archive_file.function_source.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = data.archive_file.function_source.output_path
}

# Deploy Cloud Function (Gen 2)
resource "google_cloudfunctions2_function" "telegram_bot" {
  name        = "telegram-transcribe-bot"
  location    = var.region
  description = "Telegram bot for audio transcription using Gemini AI"

  build_config {
    runtime     = "python311"
    entry_point = "webhook"

    source {
      storage_source {
        bucket = google_storage_bucket.function_bucket.name
        object = google_storage_bucket_object.function_source.name
      }
    }
  }

  service_config {
    max_instance_count    = 10
    min_instance_count    = 0
    available_memory      = "512Mi"
    timeout_seconds       = 540
    service_account_email = google_service_account.function_sa.email

    environment_variables = {
      DEPLOYMENT_MODE = "gcp"
    }

    secret_environment_variables {
      key        = "galebach_transcriber_bot_token"
      project_id = var.project_id
      secret     = google_secret_manager_secret.telegram_bot_token.secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "GOOGLE_AI_API_KEY"
      project_id = var.project_id
      secret     = google_secret_manager_secret.google_ai_api_key.secret_id
      version    = "latest"
    }
  }

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_service.cloudbuild,
    google_secret_manager_secret_version.telegram_bot_token_version,
    google_secret_manager_secret_version.google_ai_api_key_version,
  ]
}

# Make the function publicly accessible
resource "google_cloud_run_service_iam_member" "invoker" {
  location = google_cloudfunctions2_function.telegram_bot.location
  service  = google_cloudfunctions2_function.telegram_bot.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
