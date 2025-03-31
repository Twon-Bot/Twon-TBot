import os
import openai
import discord
from discord.ext import commands

class AIArtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Load your OpenAI API key from environment variables
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("Warning: OPENAI_API_KEY environment variable not set.")
        openai.api_key = self.api_key

    @commands.command()
    async def aiart(self, ctx, *, prompt: str = "a happy tree in a fantasy forest"):
        """
        Generates an AI image based on a text prompt and sends the image URL.
        Usage: !!aiart <your prompt here>
        """
        await ctx.send("Generating your AI artwork, please wait...")
        try:
            # Call the OpenAI Image API with the given prompt
            response = openai.Image.create(
                prompt=prompt,
                n=1,
                size="512x512"
            )
            # Extract the URL of the generated image
            image_url = response["data"][0]["url"]
            await ctx.send(f"Here is your AI-generated image:\n{image_url}")
        except Exception as e:
            await ctx.send(f"An error occurred while generating the image: {e}")

async def setup(bot):
    await bot.add_cog(AIArtCog(bot))
    print("Loaded AIArtCog!")
