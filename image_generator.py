import os
import base64
from io import BytesIO
from PIL import Image
import requests
from dotenv import load_dotenv

load_dotenv()

class ImageGenerator:
    def __init__(self):
        self.api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-3.5-large-turbo"
        self.headers = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_TOKEN')}"}

    def generate_image(self, prompt: str) -> str:
        """
        Generate an image from a text prompt using Stable Diffusion
        Returns: Base64 encoded image string
        """
        try:
            print(f"Generating image for prompt: {prompt}")
            
            # Make request to Hugging Face API
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={"inputs": prompt}
            )
            
            # Check if request was successful
            response.raise_for_status()
            print(f"API Response status: {response.status_code}")
            
            # Convert binary response to base64 string
            image_bytes = response.content
            print(f"Received image bytes: {len(image_bytes)} bytes")
            
            image = Image.open(BytesIO(image_bytes))
            print(f"Image opened successfully: {image.size}, mode: {image.mode}")
            
            # Convert to RGB if image is in RGBA mode
            if image.mode == 'RGBA':
                image = image.convert('RGB')
                print("Converted image to RGB mode")
            
            # Save image to base64 string
            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            print(f"Converted to base64 string, length: {len(img_str)}")
            
            # Save a test copy locally for debugging
            test_path = "static/test_image.jpg"
            os.makedirs(os.path.dirname(test_path), exist_ok=True)
            image.save(test_path)
            print(f"Saved test image to: {test_path}")
            
            return img_str
            
        except Exception as e:
            print(f"Error generating image: {str(e)}")
            raise 