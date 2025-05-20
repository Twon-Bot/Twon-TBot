import discord
from discord.ext import commands
import random

class HappyTreeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def happytree(self, ctx):
        """Sends a random happy tree drawing."""
        trees = [
            # Tree 1: A festive, stylized tree
            r"""
               ,@@@@@@@,
       ,,,.   ,@@@@@@/@@,  .oo8888o.
    ,&%%&%&&%,@@@@@/@@@@@@,8888\88/8o
   ,%&\%&&%&&%,@@@\@@@/@@@88\88888/88'
   %&&%&%&/%&&%@@\@@/ /@@@88888\88888'
   %&&%/ %&%%&&@@\ V /@@' `88\8 `/88'
   `&%\ ` /%&'    |.|        \ '|8'
       |o|        | |         | |
       |.|        | |         | |
    \/ ._\//_/__/  ,\_//__/.  \_//__/
            """,
            # Tree 2: A cute tree with leaves and trunk
            r"""
                 &&& &&  & &&
              && &\/&\|& ()|/ @, &&
              &\/(/&/&||/& /_/)_&/_&
           &() &\/&|()|/&\/ '%" & ()
          &_\_&&_\ |& |&&/&__%_/_& &&
        &&   && & &| &| /& & % ()& /&&
         ()&_---()&\&\|&&-&&--%---()~
             &&     \|||
                     |||
                     |||
                     |||
               , -=-~  .-^- _
            """,
            # Tree 3: A more natural, free-form tree
            r"""
               ccee88oo
            C8O8O8Q8PoOb o8oo
         dOB69QO8PdUOpugoO9bD
       CgggbU8OU qOp qOdoUOdcb
           6OuU  /p u gcoUodpP
              \\//  /douUP
                \\////
                 |||/\
                 |||\/
                 |||||
           .....//||||\....        
            """
        ]
        tree = random.choice(trees)
        await ctx.send(f"Here's your happy tree:\n{tree}")

async def setup(bot):
    await bot.add_cog(HappyTreeCog(bot))
    print("Loaded HappyTreeCog!")
