import colorsys
import inspect
import json
import math
import random
from typing import Optional, List
import time
import dataset
from dataclasses import dataclass
from dataset import Table
from discord import Message, Embed, Member
from discord.ext import commands
from discord.ext.commands import Context

with open("config.json") as f:
    config = json.load(f)

bot = commands.Bot(command_prefix="t$", help_command=None)

db = dataset.connect("sqlite:///economy")
users: Table = db["users"]
games: Table = db["ttt_games"]


@dataclass()
class Field:
    name: str
    value: str
    inline: bool = True


async def send_embed(
    ctx,
    message: Optional[str] = None,
    colour: Optional[str] = None,
    title: Optional[str] = None,
    footer: Optional[str] = None,
    image: Optional[str] = None,
    thumbnail: Optional[str] = None,
    fields: Optional[List[Field]] = None,
) -> Message:
    hue, sat, light = (random.random(), 0.6, 0.5)
    red, green, blue = [int(255 * i) for i in colorsys.hls_to_rgb(hue, light, sat)]
    rd_col = "{:02x}{:02x}{:02x}".format(red, green, blue)
    embed = Embed(
        description=message,
        color=(int(rd_col, 16) if not colour else int(colour, 16)),
        title=title,
    )
    if footer:
        embed.set_footer(text=footer)
    if image:
        embed.set_image(url=image)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if fields:
        for field in fields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)

    return await ctx.send(embed=embed)


@bot.event
async def on_ready():
    for command in bot.commands:
        usage = []
        for p_name, parameter in command.clean_params.items():
            default = parameter.default
            if default != inspect.Parameter.empty:
                if default is None:
                    usage.append("[{}]".format(p_name))
                else:
                    usage.append("[{} = {}]".format(p_name, default))
            else:
                usage.append("<{}>".format(p_name))
        command.usage = " " + " ".join(usage) if usage else ""

        if not command.brief:
            command.brief = "No description given."

        if not command.help:
            command.help = "No description given."

    print("Logged on as", bot.user)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    row = users.find_one(id=message.author.id)
    if not row:
        users.insert(dict(id=message.author.id, nick=message.author.name, balance=0))

    if bot.is_ready():
        await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    error = getattr(error, "original", error)

    if isinstance(error, commands.UserInputError):
        error_msg = str(error).split(" ")
        arg = error_msg.pop(0)
        await send_embed(
            ctx,
            "`<{}>` {}".format(arg, " ".join(error_msg)),
            title="Missing argument",
            colour="ff0000",
            footer="Use !help {} for more information.".format(ctx.command.name),
        )

    if isinstance(error, ValueError):
        await send_embed(ctx, "You must enter an integer.", colour="ff0000")

    if isinstance(error, commands.MissingPermissions):
        await send_embed(ctx, str(error), colour="ff0000", title="Missing permissions")


class Miscellaneous(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(
        brief="Make the bot repeat your message",
        help="Why are you using this command, are you seriously " "that bored? SMH.",
    )
    async def say(self, ctx: Context, *, message):
        await send_embed(ctx, message)

    @commands.command(
        brief="Roll a dice of any size!",
        aliases=["dice"],
        help="Roll any sided die, defaults to 6 sides.",
    )
    async def roll(self, ctx: Context, sides: int = 6):
        await send_embed(
            ctx,
            "You rolled {} on a {} sided die".format(random.randint(1, sides), sides),
        )

    @commands.command(
        brief="Ask the 8ball a question!",
        aliases=["8ball"],
        help="Ask the 8ball a question and you'll get a witty-ish response",
    )
    async def eight_ball(self, ctx: Context, *, question: str):
        options = [
            "No chance what so ever",
            "Why is that a question you're asking?!! NO.",
            "Probably not",
            "That was so retarded i don't have a response, try again",
            "Try again later, i might care then.",
            "You should sleep instead of asking questions",
            "Probably",
            "There might be a chance you know",
            "100% without a doubt",
            "Yeah sure, whatever...",
        ]

        await send_embed(
            ctx,
            "**You asked:** {}\n**8ball's verdict:** {}".format(
                question, random.choice(options)
            ),
            title="{} channels the 8ball...".format(ctx.author.name),
        )

    @commands.command(
        brief="Shows all the commands!",
        help="Shows all the commands available. Using a command name as an argument shows all the information about "
        "that command. You already know what to do since you can see this message :)",
        aliases=["info", "information", "commands", "cmds"],
    )
    async def help(self, ctx: Context, cmd: Optional[str] = None):

        if cmd:
            command = bot.get_command(cmd)
            if not command:
                await send_embed(
                    ctx,
                    "That command does not exist. Make sure you typed it in correctly!",
                    footer="Use {}help to view a list of commands!".format(
                        bot.command_prefix
                    ),
                    title="Invalid input.",
                    colour="ff0000",
                )
            else:
                await send_embed(
                    ctx,
                    title="{}{}{}".format(
                        bot.command_prefix, command.name, command.usage
                    ),
                    fields=[
                        Field("Category", command.cog_name),
                        Field(
                            "Aliases",
                            ", ".join(command.aliases) if command.aliases else "None",
                        ),
                        Field("Description", command.help, False),
                    ],
                )
        else:
            fields = []
            for name, cog in bot.cogs.items():
                cmd_info = []
                for command in cog.get_commands():
                    if command.hidden:
                        continue
                    cmd_info.append(
                        "`{}{}{}` - {}".format(
                            bot.command_prefix,
                            command.name,
                            command.usage,
                            command.brief,
                        )
                    )
                cmd_info = "\n".join(cmd_info)
                fields.append(Field(name, cmd_info, False))
            await send_embed(
                ctx,
                "Use `{}help [command]` for more information on a command. `<>` arguments are compulsory and `[]` are "
                "optional.".format(bot.command_prefix),
                fields=fields,
                title="Here's a list of commands!",
            )


class Economy(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(
        brief="Access your bank account!",
        aliases=["balance", "account"],
        help="Used to check your balance. Shows the amount of money you currently own.",
    )
    async def bal(self, ctx: Context):
        row = users.find_one(id=ctx.author.id)
        await send_embed(
            ctx,
            title="{}'s balance".format(ctx.author.name),
            fields=[
                Field("Balance", "**£{}**".format(row["balance"])),
                Field("In bank", "**£{}**".format(row["bank"])),
            ],
            thumbnail="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/facebook/65/money"
            "-bag_1f4b0.png",
            footer="You have £{} in total.".format(row["balance"] + row["bank"]),
        )

    @commands.command(aliases=["add", "add_money"], hidden=True)
    @commands.is_owner()
    async def gain(self, ctx: Context, amount):
        row = users.find_one(id=ctx.author.id)
        new_bal = row["balance"] + int(amount)
        users.update(dict(id=ctx.author.id, balance=new_bal), ["id"])
        await send_embed(
            ctx,
            "{}, I have added **£{}** to your account\nNew balance: **£{}**".format(
                ctx.author.name, amount, new_bal
            ),
        )

    @commands.command(
        brief="Gamble your money!",
        help="Put your money on the line in hopes to double the amount you enter. "
        "A roll over 50 (excluding) is a win",
    )
    async def gamble(self, ctx: Context, amount):
        row = users.find_one(id=ctx.author.id)

        if int(amount) > row["balance"]:
            await send_embed(
                ctx,
                "You cannot gamble more than you have.\nBalance: £{}".format(
                    row["balance"]
                ),
            )
        elif int(amount) < 5:
            await send_embed(ctx, "Minimum bet is <:messMoney:440105828758978590>5")
        else:
            num = random.randint(1, 100)
            new_bal = row["balance"]
            if num <= 50:
                new_bal -= int(amount)
                msg = "Unfortunately you rolled **{}**. You lost **£{}**".format(
                    num, amount
                )
            else:
                new_bal += int(amount)
                msg = "Congrats! you rolled **{}**. You won **£{}**".format(num, amount)

            users.update(dict(id=ctx.author.id, balance=new_bal), ["id"])
            await send_embed(ctx, "{}\nBalance: **£{}**".format(msg, new_bal))

    @commands.command(
        brief="Claim some money each day!",
        help="Add a random amount of money between <:messMoney:440105828758978590>100 and <:messMoney:440105828758978590>500 to your balance each day",
        aliases=["daily"],
    )
    async def claim(self, ctx: Context):
        row = users.find_one(id=ctx.author.id)

        if int(time.time()) < row["claim_cd"] + 86400:
            seconds = 86400 - (int(time.time()) - row["claim_cd"])
            hours = math.floor(seconds / 3600)
            seconds -= hours * 3600
            minutes = math.floor(seconds / 60)
            seconds -= minutes * 60
            await send_embed(
                ctx,
                "That command is on cool-down! Time remaining: **{}** hours, **{}** minutes and **{}** seconds".format(
                    hours, minutes, seconds
                ),
                title="Not so fast!",
                colour="ff0000",
                thumbnail="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/facebook/65/alarm"
                "-clock_23f0.png ",
            )
        else:
            money = random.randint(100, 500)
            new_bal = row["balance"] + money
            responses = [
                "You beat up a poor homeless man and stole his lunch money, no regrets were made as you cashed out "
                "**£{}**. Why'd he have so much money the damn hoarder.",
                "You shot up an orphanage and sniped their donation box, turns out they were stashing it away. "
                "You stole **£{}** and no one complained.",
                "You saw a poster on the wall advertising a cheese tasting session, when you arrived, you were "
                "kidnapped by the fucking Italian Mafia and they sauced you **£{}** in exchange for your loyalty.",
                "You literally sucked dick for money. He paid you **£{}**. Money is money right...",
            ]
            users.update(
                dict(id=ctx.author.id, balance=new_bal, claim_cd=int(time.time())),
                ["id"],
            )
            await send_embed(
                ctx,
                random.choice(responses).format(money)
                + " Come back tomorrow for more money!",
                title="Daily money claimed!",
                thumbnail="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/facebook/65/banknote"
                "-with-dollar-sign_1f4b5.png",
            )

    @commands.command(
        brief="Deposit money into your bank!",
        help="Stores your money into your bank",
        aliases=["dep"],
    )
    async def deposit(self, ctx: Context, amount: int):
        row = users.find_one(id=ctx.author.id)
        if amount > row["balance"]:
            await send_embed(
                ctx,
                "You cannot deposit more than you own.\nBalance: **£{}**".format(
                    row["balance"]
                ),
                title="Deposit failed.",
                colour="ff0000",
                thumbnail="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/facebook/65/cross"
                "-mark_274c.png",
            )
        else:
            new_bal = row["balance"] - amount
            new_banked = row["bank"] + amount
            users.update(
                dict(id=ctx.author.id, bank=new_banked, balance=new_bal,), ["id"],
            )
            await send_embed(
                ctx,
                "Successfully deposited **£{}** to your bank account!\nBalance: **£{}**\nMoney in bank: **£{}**".format(
                    amount, new_bal, new_banked
                ),
                title="Money deposited!",
                thumbnail="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/facebook/65"
                "/downwards-black-arrow_2b07.png",
            )

    @commands.command(
        brief="Withdraw money from your bank!",
        help="Takes money out of your bank and into your balance",
        aliases=["wd"],
    )
    async def withdraw(self, ctx: Context, amount: int):
        row = users.find_one(id=ctx.author.id)
        if amount > row["bank"]:
            await send_embed(
                ctx,
                "You cannot withdraw more than you have in the bank.\nMoney in bank: **£{}**".format(
                    row["bank"]
                ),
                title="Withdraw failed.",
                colour="ff0000",
            )
        else:
            new_bal = row["balance"] + amount
            new_banked = row["bank"] - amount
            users.update(
                dict(id=ctx.author.id, bank=new_banked, balance=new_bal), ["id"],
            )
            await send_embed(
                ctx,
                "Successfully withdrew **£{}** from your bank account!"
                "\nBalance: **£{}**"
                "\nMoney in bank: **£{}**".format(amount, new_bal, new_banked),
                title="Money withdrawn!",
                thumbnail="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/facebook/65/upwards"
                "-black-arrow_2b06.png",
            )

    @commands.command()
    @commands.is_owner()
    async def rc(self, ctx):
        db.query("UPDATE users SET claim_cd = 0")


class Games(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(
        brief="Play a game of Tic Tac Toe!",
        help="Starts a Tic Tac Toe game. Use `{0}accept <game id>` to accept a game, "
        "then to put a cross/nought use `{0}place <position>` and use `{0}end` to end "
        "the game if needed.".format(bot.command_prefix),
        aliases=["tictactoe"],
    )
    async def ttt(self, ctx: Context):
        row = games.find_one(
            (games.table.c.noughts == ctx.author.id)
            | (games.table.c.crosses == ctx.author.id)
        )

        if not row:
            games.insert(dict(crosses=ctx.author.id, guild_id=ctx.guild.id))
            game_id = games.find_one(crosses=ctx.author.id)["game_id"]
            await send_embed(
                ctx,
                "{} has started a Tic Tac Toe game! Type `!accept {}` to join.".format(
                    ctx.author.name, game_id
                ),
            )
        else:
            await send_embed(ctx, "You are already in a game!")

    @commands.command(hidden=True)
    async def accept(self, ctx: Context, game_id: int):
        row = games.find_one(game_id=game_id)
        in_game = games.find_one(
            (games.table.c.noughts == ctx.author.id)
            | (games.table.c.crosses == ctx.author.id)
        )

        if not row:
            await send_embed(ctx, "Invalid game id, or that game doesn't exist.")
        elif ctx.author.id == row["crosses"]:
            await send_embed(ctx, "You cannot join your own game!")
        elif in_game:
            await send_embed(ctx, "You are already in a game!")
        else:
            games.update(dict(game_id=game_id, noughts=ctx.author.id), ["game_id"])
            await send_embed(
                ctx,
                "You have successfully joined the game! <@{}> type `!place <position>` to start!".format(
                    row["crosses"]
                ),
            )
            ttt_message: Message = await send_embed(
                ctx,
                "```"
                "1 | 2 | 3\t\t\t Type !place <position> to play your turn.\n"
                "---------\t\t\t Get three in a row/diagonal to win.\n"
                "4 | 5 | 6\t\t\t It is currently crosses' turn.\n"
                "---------\t\t\t Type !end to end the game.\n"
                "7 | 8 | 9\n"
                "```",
            )

            games.update(dict(game_id=game_id, message=ttt_message.id), ["game_id"])

    @commands.command(hidden=True)
    async def place(self, ctx: Context, arg):
        row = games.find_one(
            (games.table.c.noughts == ctx.author.id)
            | (games.table.c.crosses == ctx.author.id)
        )

        if not row:
            await send_embed(ctx, "You are not in a game! Type `!ttt` to start one.")
            return
        elif not row["message"]:
            await send_embed(ctx, "The game hasn't started yet!")
            return
        elif row[row["turn"]] != ctx.author.id:
            await send_embed(ctx, "It is not your turn.")
            return
        elif arg not in [str(i) for i in range(1, 10)]:
            await send_embed(ctx, "Invalid argument, type a number from 1 - 9")
            return

        cmd = await ctx.fetch_message(ctx.message.id)
        await cmd.delete()

        symbol = "X" if row["turn"] == "crosses" else "O"
        positions = games.find_one(game_id=row["game_id"])["positions"]
        p = json.loads(positions)
        if p[arg] == "X" or p[arg] == "O":
            await send_embed(ctx, "That spot is already taken!")
            return
        else:
            p[arg] = symbol
        p = json.dumps(p)
        games.update(dict(game_id=row["game_id"], positions=p), ["game_id"])

        positions = games.find_one(game_id=row["game_id"])["positions"]
        p = json.loads(positions)

        def end_game():
            games.delete(game_id=row["game_id"])

        msg = await ctx.fetch_message(row["message"])
        await msg.edit(
            embed=Embed(
                description="```"
                "{0} | {1} | {2}\t\t Type !place <position> to play your turn\n"
                "---------\t\t Get three in a row/diagonal to win.\n"
                "{3} | {4} | {5}\t\t It is currently {9}' turn.\n"
                "---------\n"
                "{6} | {7} | {8}\n"
                "```".format(
                    p["1"],
                    p["2"],
                    p["3"],
                    p["4"],
                    p["5"],
                    p["6"],
                    p["7"],
                    p["8"],
                    p["9"],
                    row["turn"],
                ),
                colour=msg.embeds[0].colour,
            )
        )

        for h in [
            p["1"] + p["2"] + p["3"],
            p["4"] + p["5"] + p["6"],
            p["7"] + p["8"] + p["9"],
        ]:
            if h == "XXX":
                await send_embed(ctx, "<@{}> has won on Rows!".format(row["crosses"]))
                end_game()
                return
            elif h == "OOO":
                await send_embed(ctx, "<@{}> has won on Rows!".format(row["noughts"]))
                end_game()
                return

        for v in [
            p["1"] + p["4"] + p["7"],
            p["2"] + p["5"] + p["8"],
            p["3"] + p["6"] + p["9"],
        ]:
            if v == "XXX":
                await send_embed(
                    ctx, "<@{}> has won on Columns!".format(row["crosses"])
                )
                end_game()
                return
            elif v == "OOO":
                await send_embed(
                    ctx, "<@{}> has won on Columns!".format(row["noughts"])
                )
                end_game()
                return

        for d in [p["1"] + p["5"] + p["9"], p["3"] + p["5"] + p["7"]]:
            if d == "XXX":
                await send_embed(
                    ctx, "<@{}> has won on Diagonals!".format(row["crosses"])
                )
                end_game()
                return
            elif d == "OOO":
                await send_embed(
                    ctx, "<@{}> has won on Diagonals!".format(row["noughts"])
                )
                end_game()
                return

        if " " not in p.values():
            await send_embed(ctx, "It ended in a tie!")
            end_game()
            return

        next_turn = "noughts" if row["turn"] == "crosses" else "crosses"
        games.update(dict(game_id=row["game_id"], turn=next_turn), ["game_id"])

    @commands.command(hidden=True)
    async def end(self, ctx: Context):
        row = games.find_one(
            (games.table.c.noughts == ctx.author.id)
            | (games.table.c.crosses == ctx.author.id)
        )

        if not row:
            await send_embed(ctx, "You are not in a game! Type `!ttt` to start one.")
        else:
            games.delete(game_id=row["game_id"])
            await send_embed(ctx, "{} has ended the game.".format(ctx.author.name))


class Moderation(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(
        brief="Ban a user from the server",
        help="Ban a user from the server, requires ban member permissions, use an @ mention for the member argument.",
        aliases=["hammer"],
    )
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: Context, member: Member, *, reason: Optional[str] = None):
        await ctx.guild.ban(member, reason=reason)
        await send_embed(
            ctx,
            "{} has been banned for: {}".format(member.name, reason),
            title="The ban hammer has spoken!",
        )

    @commands.command(
        brief="Unban a user from the server",
        help="Unbans a user from the server, requires ban member permissions, use an id or their full name for the "
        "member argument. Use `{}ban_list` to find a list of members who are banned.".format(
            bot.command_prefix
        ),
        aliases=["ub", "free"],
    )
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: Context, member, *, reason: Optional[str] = None):
        user = None
        try:
            user_id = int(member)
            user = await bot.fetch_user(user_id)
        except ValueError:
            name, discrim = member.split("#")
            for ban in await ctx.guild.bans():
                if name == ban.user.name and discrim == ban.user.discriminator:
                    user = ban.user

        if not user:
            await send_embed(
                ctx,
                "`<member>` should be an id or a name in the form `<name>#<discrim>` i.e Murumu1#7994",
                title="Invalid input",
                colour="ff0000",
            )

        await ctx.guild.unban(user, reason=reason)
        await send_embed(
            ctx, "{} has been unbanned!".format(user.name),
        )

    @commands.command(
        brief="Kick a user from the server",
        help="Kick a user from the server, requires ban member permissions, use an @ mention for the member argument.",
        aliases=["boot"],
    )
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: Context, member: Member, *, reason: Optional[str] = None):
        await ctx.guild.kick(member, reason=reason)
        await send_embed(ctx, "{} has been kicked!".format(member.name))

    @commands.command(
        brief="Shows a list of banned members",
        help="Shows all banned members in the server, with their username and their id. Useful for `{}unban`".format(
            bot.command_prefix
        ),
        aliases=["bl", "bans"],
    )
    @commands.has_permissions(ban_members=True)
    async def ban_list(self, ctx: Context):
        bans = await ctx.guild.bans()
        if not bans:
            await send_embed(
                ctx,
                "There are no bans on this server!",
                title="No bans found.",
                colour="ff0000",
            )
        else:
            msg = "Username:{} ID:".format(7 * "\t")
            for ban in bans:
                full_name = "{}#{}".format(ban.user.name, ban.user.discriminator)
                tab_space = 9 - math.floor(len(full_name) / 4)
                msg += "\n{}{}{}".format(full_name, tab_space * "\t", ban.user.id)

            await ctx.send("```{}```".format(msg))


for c in [Miscellaneous, Economy, Games, Moderation]:
    bot.add_cog(c(bot))

bot.run(config["token"])
db.close()
