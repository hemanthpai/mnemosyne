import uuid

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test memory extraction with sample conversation"

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=str, help="User ID for testing")

    def handle(self, *args, **options):
        user_id = options.get("user_id") or str(uuid.uuid4())

        sample_conversation = """
        User: Hi! I'm John, a software engineer living in San Francisco. 
        I love hiking and photography in my free time. My favorite programming 
        language is Python, and I'm currently working on a machine learning project 
        about natural language processing. I have a cat named Whiskers who loves 
        to sit on my keyboard while I code.
        
        Assistant: That's great! It sounds like you have a nice balance between 
        work and hobbies. How long have you been working in machine learning?
        
        User: About 3 years now. I started after getting my Master's degree in 
        Computer Science from Stanford. I really want to specialize in AI safety 
        and work for a company like Anthropic or OpenAI someday.
        """

        from rest_framework.test import APIRequestFactory

        from memories.views import ExtractMemoriesView

        factory = APIRequestFactory()
        request = factory.post(
            "/extract/", {"conversation_text": sample_conversation, "user_id": user_id}
        )

        view = ExtractMemoriesView()
        response = view.post(request)

        self.stdout.write(f"Response status: {response.status_code}")
        self.stdout.write(f"Response data: {response.data}")

        if response.data.get("success"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Successfully extracted {response.data['memories_extracted']} memories"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"✗ Extraction failed: {response.data.get('error')}")
            )
