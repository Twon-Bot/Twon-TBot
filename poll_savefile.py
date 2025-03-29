import discord
from discord.ext import commands
import csv

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_votes = {}  # Store user votes
        self.total_votes = 0  # Track total votes
        self.options = []  # Store poll options
        self.vote_count = {}  # Track count for each option

    @commands.command()
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
    async def poll(self, ctx, *, args: str):
        """
        Create a poll. Defaults to single voting.
        To create a multiple voting poll, use !!poll multiple <question> | <option1> | <option2> | ...
        """
        # Check if the first argument is "multiple" to set the voting type
        if args.startswith("multiple"):
            voting_type = "multiple"
            args = args[len("multiple "):].strip()  # Remove "multiple " from args
        else:
            voting_type = "single"

        # Split the input into parts
        parts = args.split('|')  # Use | as a delimiter for options
        question = parts[0].strip()  # First part is the question
        self.options = [opt.strip() for opt in parts[1:]]  # Store options for results display

        if len(self.options) < 2 or len(self.options) > 4:
            await ctx.send("Please provide between 2 to 4 options for the poll.")
            return

        # Initialize vote count for options
        self.vote_count = {option: 0 for option in self.options}

        # Create buttons for each option with only letter emojis
        buttons = [discord.ui.Button(label=f"{chr(127462 + i)}", custom_id=option) for i, option in enumerate(self.options)]

        # Create the view and add buttons
        view = discord.ui.View()
        for button in buttons:
            view.add_item(button)

        # Send the initial poll message as an embed
        embed = discord.Embed(
            title="📊 " + question,
            color=0xfe407d  # Use the specified color
        )
        
        # Add initial options to the embed with bold formatting and spacing
        result_message = self.format_poll_results()
        embed.add_field(name="\u200b", value=result_message, inline=False)  # Use a zero-width space to avoid an empty line

        # Send the initial poll message
        self.poll_message = await ctx.send(embed=embed, view=view)

        # Define button click handler
        async def button_callback(interaction: discord.Interaction):
            user_id = interaction.user.id  # Get the user's ID

            try:
                if voting_type == 'single':
                    # If it's single voting, check if the user has already voted
                    previous_vote = self.user_votes.get(user_id)
                    if previous_vote:
                        # If the user has a previous vote, decrement the count for that option
                        self.total_votes -= 1  # Decrease total votes count
                        await self.update_vote_count(previous_vote, -1)  # Decrement the previous option count

                    # Set the new vote and increment the count for the new option
                    self.user_votes[user_id] = interaction.data['custom_id']
                    self.total_votes += 1  # Increase total votes count
                    await self.update_vote_count(interaction.data['custom_id'], 1)  # Increment the new option count
                    await interaction.response.send_message(f"You voted for: {interaction.data['custom_id']}", ephemeral=True)

                elif voting_type == 'multiple':
                    # If it's multiple voting, add to the user's selected options
                    if user_id not in self.user_votes:
                        self.user_votes[user_id] = []
                    selected_option = interaction.data['custom_id']
                    if selected_option not in self.user_votes[user_id]:
                        self.user_votes[user_id].append(selected_option)
                        self.total_votes += 1
                    await interaction.response.send_message(f"You added your vote for: {selected_option}", ephemeral=True)

                # Update results display
                await self.update_results(ctx)

            except Exception as e:
                print(f"Failed to send interaction response: {e}")

        # Add the callback to each button
        for button in buttons:
            button.callback = button_callback

    async def update_vote_count(self, option, increment):
        """Update the count for the specified option."""
        if option in self.vote_count:
            self.vote_count[option] += increment  # Increment or decrement the count

    async def update_results(self, ctx):
        """Update the results message with the current voting status."""
        # Create a formatted result message
        result_message = self.format_poll_results()

        # Update the poll message with the new results
        embed = discord.Embed(
            title="📊 " + self.poll_message.embeds[0].title,  # Keep the original title (question)
            color=0xfe407d  # Use the specified color
        )
        embed.add_field(name="\u200b", value=result_message, inline=False)  # (NEED THIS) Use a zero-width space to avoid an empty line
        await self.poll_message.edit(embed=embed)

    def format_poll_results(self):
        """Format the poll results into a string with emojis and adjusted output."""
        result_message = ""
        for i, option in enumerate(self.options):
            count = self.vote_count.get(option, 0)  # Get the current count for each option
            percentage = (count / self.total_votes * 100) if self.total_votes > 0 else 0
            bar_length = int(13 * percentage // 100)  # Scale to 13 characters for the bar (2/3 of 20)
            
            # Using letter emojis for options
            emoji_letter = f"{chr(127462 + i)}"  # This will get the corresponding regional indicator symbol
            result_message += f"**{emoji_letter} {option}**\n"  # Bold the option and add spacing
            result_message += f"[{'█' * bar_length}{'▒' * (13 - bar_length)}] | {percentage:.1f}% ({count})\n\n"  # Solid bar appearance

        return result_message

    @commands.command()
    @commands.has_any_role('Moderator', 'Manager', 'Server Owner')
    async def export_votes(self, ctx):
        """Export the user votes to a CSV file."""
        if not self.user_votes:
            await ctx.send("No votes to export.")
            return

        # Define the CSV file name
        file_name = "poll_votes.csv"

        # Write the votes to a CSV file
        with open(file_name, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['User ID', 'Selected Options'])  # Header row

            for user_id, options in self.user_votes.items():
                user_id_str = f"'{user_id}"  # Ensure it's treated as text in CSV
                if isinstance(options, list):
                    options_str = ', '.join(options)  # Join multiple options into a string
                else:
                    options_str = options  # Single option
                writer.writerow([user_id_str, options_str])  # Write user ID and their votes

        # Send the CSV file to the user
        await ctx.send(file=discord.File(file_name))

# This is where the cog is added to the bot
async def setup(bot):
    await bot.add_cog(PollCog(bot))
    print("Loaded PollCog!")  # This should print when the cog is loaded
