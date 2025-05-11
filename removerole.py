import discord
from discord.ext import commands

# The only role ID this command will ever remove:
TARGET_ROLE_ID = 1366303580591755295

class RemoveRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name='removerole',
        aliases=['rr', 'remr', 'remove', 'rrole']
    )
    @commands.has_any_role('Manager', 'Server Owner', 'Moderator', 'The BotFather')
    async def removerole(
        self,
        ctx: commands.Context,
        role_id: int = None
    ):
        """
        Removes the one designated role from every member who currently has it.
        
        Usage: !!removerole <role ID>
        """
        # 1) Check that an ID was provided
        if role_id is None:
            await ctx.send(
                "⚠️ **Error:** You must provide the role ID to remove.\n"
                "**Usage:** `!!removerole 1366303580591755295`"
            )
            return

        # 2) Enforce the failsafe: only allow the specific target role
        if role_id != TARGET_ROLE_ID:
            await ctx.send(
                f"❌ That role ID (`{role_id}`) cannot be removed by this command.\n"
                f"Only role `{TARGET_ROLE_ID}` may be removed."
            )
            return

        # 3) Look up the role object in the guild
        guild = ctx.guild
        role = guild.get_role(TARGET_ROLE_ID)
        if role is None:
            await ctx.send(f"❌ Could not find a role with ID `{TARGET_ROLE_ID}` in this server.")
            return

        # 4) Collect members who currently have the role
        members_with_role = role.members
        if not members_with_role:
            await ctx.send(f"ℹ️ No one currently has the `{role.name}` role.")
            return

        # 5) Remove the role from each member
        failed = []
        for member in members_with_role:
            try:
                await member.remove_roles(role, reason="Bulk removerole command issued")
            except Exception:
                failed.append(member)

        # 6) Report results
        if failed:
            failed_list = ", ".join(m.mention for m in failed)
            await ctx.send(
                f"⚠️ Removed `{role.name}` from most users, but failed on: {failed_list}"
            )
        else:
            await ctx.send(
                f"✅ Successfully removed `{role.name}` from {len(members_with_role)} member"
                f"{'s' if len(members_with_role) != 1 else ''}."
            )

    @removerole.error
    async def removerole_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(
                "⚠️ **Error:** Invalid role ID. Please make sure you passed a numeric ID.\n"
                "**Usage:** `!!removerole 1366303580591755295`"
            )
        elif isinstance(error, commands.MissingAnyRole):
            await ctx.send("❌ You do not have permission to use this command.")
        else:
            await ctx.send("⚠️ An unexpected error occurred while processing the command.")

async def setup(bot):
    await bot.add_cog(RemoveRoleCog(bot))
    print("Loaded RemoveRoleCog!")  
