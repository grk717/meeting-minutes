// audio/transcription/custom_asr_provider.rs
//
// Custom ASR endpoint provider implementation.
// Sends audio to a user-configured OpenAI-compatible /audio/transcriptions endpoint.

use super::provider::{TranscriptionError, TranscriptionProvider, TranscriptResult};
use async_trait::async_trait;
use log::{error, info};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;

/// Configuration for a custom ASR endpoint (OpenAI-compatible)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CustomASRConfig {
    /// Base URL of the OpenAI-compatible API endpoint (e.g., "https://api.openai.com/v1")
    pub endpoint: String,
    /// API key for authentication (optional if server doesn't require it)
    #[serde(rename = "apiKey")]
    pub api_key: Option<String>,
    /// Model identifier to use (e.g., "whisper-1")
    pub model: String,
    /// Language hint for transcription (e.g., "en")
    pub language: Option<String>,
}

/// Response from an OpenAI-compatible transcription endpoint
#[derive(Debug, Deserialize)]
struct TranscriptionResponse {
    text: String,
}

/// Custom ASR provider that sends audio to a remote OpenAI-compatible endpoint
pub struct CustomASRProvider {
    config: Arc<RwLock<CustomASRConfig>>,
    client: reqwest::Client,
}

impl CustomASRProvider {
    pub fn new(config: CustomASRConfig) -> Result<Self, String> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

        Ok(Self {
            config: Arc::new(RwLock::new(config)),
            client,
        })
    }

    /// Encode f32 audio samples to WAV bytes (16-bit PCM)
    pub fn encode_wav(samples: &[f32], sample_rate: u32) -> Vec<u8> {
        let num_channels: u16 = 1;
        let bits_per_sample: u16 = 16;
        let byte_rate = sample_rate * num_channels as u32 * bits_per_sample as u32 / 8;
        let block_align = num_channels * bits_per_sample / 8;

        // Convert f32 samples to i16
        let pcm_data: Vec<i16> = samples
            .iter()
            .map(|&s| {
                let clamped = s.clamp(-1.0, 1.0);
                (clamped * 32767.0) as i16
            })
            .collect();

        let data_size = (pcm_data.len() * 2) as u32;
        let file_size = 36 + data_size;

        let mut wav = Vec::with_capacity(44 + data_size as usize);

        // RIFF header
        wav.extend_from_slice(b"RIFF");
        wav.extend_from_slice(&file_size.to_le_bytes());
        wav.extend_from_slice(b"WAVE");

        // fmt chunk
        wav.extend_from_slice(b"fmt ");
        wav.extend_from_slice(&16u32.to_le_bytes()); // chunk size
        wav.extend_from_slice(&1u16.to_le_bytes()); // PCM format
        wav.extend_from_slice(&num_channels.to_le_bytes());
        wav.extend_from_slice(&sample_rate.to_le_bytes());
        wav.extend_from_slice(&byte_rate.to_le_bytes());
        wav.extend_from_slice(&block_align.to_le_bytes());
        wav.extend_from_slice(&bits_per_sample.to_le_bytes());

        // data chunk
        wav.extend_from_slice(b"data");
        wav.extend_from_slice(&data_size.to_le_bytes());
        for sample in &pcm_data {
            wav.extend_from_slice(&sample.to_le_bytes());
        }

        wav
    }
}

#[async_trait]
impl TranscriptionProvider for CustomASRProvider {
    async fn transcribe(
        &self,
        audio: Vec<f32>,
        language: Option<String>,
    ) -> std::result::Result<TranscriptResult, TranscriptionError> {
        let config = self.config.read().await;

        // Encode audio as WAV (16kHz mono, 16-bit PCM)
        let wav_bytes = Self::encode_wav(&audio, 16000);

        info!(
            "CustomASR: Sending {} samples ({:.1}s) as {:.1}KB WAV to {}",
            audio.len(),
            audio.len() as f64 / 16000.0,
            wav_bytes.len() as f64 / 1024.0,
            config.endpoint
        );

        // Build multipart form
        let file_part = reqwest::multipart::Part::bytes(wav_bytes)
            .file_name("audio.wav")
            .mime_str("audio/wav")
            .map_err(|e| {
                TranscriptionError::EngineFailed(format!("Failed to create multipart: {}", e))
            })?;

        let mut form = reqwest::multipart::Form::new()
            .part("file", file_part)
            .text("model", config.model.clone())
            .text("response_format", "json".to_string());

        // Add language if provided (prefer runtime language, fall back to config)
        let lang = language.or_else(|| config.language.clone());
        if let Some(lang) = lang {
            form = form.text("language", lang);
        }

        // Build URL: append /audio/transcriptions to the base endpoint
        let url = format!(
            "{}/audio/transcriptions",
            config.endpoint.trim_end_matches('/')
        );

        // Build request
        let mut request = self.client.post(&url).multipart(form);

        // Add authorization if API key provided
        if let Some(ref key) = config.api_key {
            if !key.trim().is_empty() {
                request = request.header("Authorization", format!("Bearer {}", key));
            }
        }

        // Send request
        let response = request.send().await.map_err(|e| {
            if e.is_timeout() {
                error!("CustomASR: Request timed out to {}", url);
                TranscriptionError::EngineFailed(
                    "Custom ASR request timed out. Check endpoint availability.".to_string(),
                )
            } else if e.is_connect() {
                error!("CustomASR: Cannot connect to {}", url);
                TranscriptionError::EngineFailed(format!(
                    "Cannot connect to custom ASR endpoint: {}",
                    url
                ))
            } else {
                error!("CustomASR: HTTP request failed: {}", e);
                TranscriptionError::EngineFailed(format!("HTTP request failed: {}", e))
            }
        })?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            error!(
                "CustomASR: HTTP {} from {}: {}",
                status, url, error_text
            );
            return Err(TranscriptionError::EngineFailed(format!(
                "Custom ASR returned HTTP {}: {}",
                status, error_text
            )));
        }

        // Parse response
        let transcription: TranscriptionResponse = response.json().await.map_err(|e| {
            error!("CustomASR: Failed to parse response: {}", e);
            TranscriptionError::EngineFailed(format!(
                "Failed to parse transcription response: {}",
                e
            ))
        })?;

        let text = transcription.text.trim().to_string();
        if !text.is_empty() {
            info!("CustomASR: Transcribed: '{}'", text);
        }

        Ok(TranscriptResult {
            text,
            confidence: None, // OpenAI-compatible endpoints don't provide confidence
            is_partial: false,
        })
    }

    async fn is_model_loaded(&self) -> bool {
        // Remote provider is always "ready" - no local model to load
        true
    }

    async fn get_current_model(&self) -> Option<String> {
        let config = self.config.read().await;
        Some(config.model.clone())
    }

    fn provider_name(&self) -> &'static str {
        "CustomASR"
    }
}
