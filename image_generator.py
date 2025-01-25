import os
import base64
from io import BytesIO
from PIL import Image
import requests

class ImageGenerator:
    def __init__(self):
        self.hf_api_key = None

    def set_api_key(self, api_key: str):
        """Set the Hugging Face API key"""
        if not api_key or not isinstance(api_key, str):
            raise ValueError("Invalid API key provided")
        self.hf_api_key = api_key

    def generate_image(self, prompt: str) -> str:
        """Generate image using Hugging Face Stable Diffusion"""
        if not self.hf_api_key:
            raise ValueError("Hugging Face API key not set. Please set it in settings.")
        
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Invalid prompt provided")

        try:
            print(f"Generating image with Hugging Face for prompt: {prompt}")
            
            headers = {"Authorization": f"Bearer {self.hf_api_key}"}
            response = requests.post(
                "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-3.5-large-turbo",
                headers=headers,
                json={"inputs": prompt},
                timeout=30  # Add timeout
            )
            
            if response.status_code == 401:
                raise ValueError("Invalid Hugging Face API key")
            elif response.status_code == 503:
                raise ValueError("Model is currently loading. Please try again in a few minutes.")
            
            response.raise_for_status()
            print(f"API Response status: {response.status_code}")
            
            image_bytes = response.content
            if not image_bytes:
                raise ValueError("No image data received from API")
                
            print(f"Received image bytes: {len(image_bytes)} bytes")
            
            image = Image.open(BytesIO(image_bytes))
            print(f"Image opened successfully: {image.size}, mode: {image.mode}")
            
            if image.mode == 'RGBA':
                image = image.convert('RGB')
                print("Converted image to RGB mode")
            
            buffered = BytesIO()
            image.save(buffered, format="JPEG", quality=85)  # Reduced quality for better performance
            img_str = base64.b64encode(buffered.getvalue()).decode()
            print(f"Converted to base64 string, length: {len(img_str)}")
            
            return img_str
            
        except requests.exceptions.Timeout:
            print("Request timed out while generating image")
            raise ValueError("Request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            print(f"Network error while generating image: {str(e)}")
            raise ValueError("Network error occurred. Please check your connection.")
        except Exception as e:
            print(f"Error generating image: {str(e)}")
            raise ValueError(f"Failed to generate image: {str(e)}")