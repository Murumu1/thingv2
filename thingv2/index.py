from dataset import Table
from discord import Message, Embed
from discord.ext import commands
import random
import typing
import dataset

import json

with open('config.json') as f:
    config = json.load(f)

bot = commands.Bot(command_prefix='!')

db = dataset.connect('sqlite:///economy')
users: Table = db['users']
games: Table = db['ttt_games']


async def send_embed(ctx, message: str,
                     colour: typing.Optional[str] = None,
                     title: typing.Optional[str] = None,
                     footer: typing.Optional[str] = None,
                     image: typing.Optional[str] = None):
    r, g, b = random.randint(120, 220), random.randint(120, 220), random.randint(120, 220)
    rd_col = "{:02x}{:02x}{:02x}".format(r, g, b)
    embed = Embed(description=message,
                  color=(int(rd_col, 16) if not colour else int(colour, 16)),
                  title=title)
    if footer:
        embed.set_footer(text=footer)
    if image:
        embed.set_image(url=image)

    return await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print('Logged on as', bot.user)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    raise error
    error = getattr(error, 'original', error)

    if isinstance(error, commands.UserInputError):
        error_msg = str(error).split(' ')
        arg = error_msg.pop(0)
        await send_embed(ctx, "`<{}>` {}".format(arg, " ".join(error_msg)),
                         title='Missing argument',
                         colour="ff0000", footer="Use !help {} for more information.".format(ctx.command.name))

    if isinstance(error, ValueError):
        await send_embed(ctx, "You must enter an integer.", colour="ff0000")


class Miscellaneous(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(brief="Make the bot repeat your message",
                      help="Why are you using this command, are you seriously "
                           "that bored? SMH.")
    async def say(self, ctx, *, message):
        await send_embed(ctx, message)

    @commands.command(brief="Roll a dice of any size!",
                      aliases=["dice"],
                      help="Roll any sided die, defaults to 6 sides.")
    async def roll(self, ctx, sides: int = 6):
        await send_embed(ctx, 'You rolled {} on a {} sided die'.format(random.randint(1, sides), sides))


class Economy(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(brief="Access your bank account!",
                      aliases=["balance", "account"],
                      help="Used to check your balance. Shows the amount of money you currently own.")
    async def bal(self, ctx):
        row = users.find_one(id=ctx.author.id)

        if not row:
            users.insert(dict(id=ctx.author.id, nick=ctx.author.name, balance=0))
            await send_embed(ctx, 'I have set up your account!\nBalance: ${}'.format(0))
            return
        else:
            await send_embed(ctx, 'Balance: ${}'.format(row['balance']))

    @commands.command(aliases=["add", "add_money"],
                      hidden=True)
    @commands.has_permissions(administrator=True)
    async def gain(self, ctx, amount):
        row = users.find_one(id=ctx.author.id)

        if not row:
            await send_embed(ctx, 'Type !bal to set up your account!')
            return
        else:
            new_bal = row['balance'] + int(amount)
            users.update(dict(id=ctx.author.id, balance=new_bal), ['id'])
            await send_embed(ctx, '{}, I have added ${} to your account\nnew bal: ${}'
                             .format(ctx.author.name, amount, new_bal))

    @commands.command(brief="Gamble your money!",
                      usage="<amount>",
                      help="Put your money on the line in hopes to double the amount you enter. "
                           "A roll over 50 (excluding) is a win")
    async def gamble(self, ctx, amount):
        row = users.find_one(id=ctx.author.id)

        if not row:
            await send_embed(ctx, 'Type !bal to set up your account!')
            return
        elif int(amount) > row['balance']:
            await send_embed(ctx, 'You cannot gamble more than you have.\nBalance: ${}'.format(row['balance']))
            return
        elif int(amount) < 5:
            await send_embed(ctx, 'Minimum bet is $5')
            return
        else:
            num = random.randint(1, 100)
            new_bal = row['balance']
            if num <= 50:
                new_bal -= int(amount)
                msg = 'Unfortunately you rolled {}. You lost ${}'.format(num, amount)
            else:
                new_bal += int(amount)
                msg = 'Congrats! you rolled {}. You won ${}'.format(num, amount)

            users.update(dict(id=ctx.author.id, balance=new_bal), ['id'])
            await send_embed(ctx, '{}\nBalance: ${}'.format(msg, new_bal))


class Games(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(brief="Play a game of Tic Tac Toe!",
                      help="Starts a Tic Tac Toe game, use !accept <gameid> to accept a game, "
                           "then to put a cross/nought use !place <position> and use !end to end "
                           "the game if needed.",
                      aliases=["tictactoe"])
    async def ttt(self, ctx):
        row = games.find_one((games.table.c.noughts == ctx.author.id) | (games.table.c.crosses == ctx.author.id))

        if not row:
            games.insert(dict(crosses=ctx.author.id, guild_id=ctx.guild.id))
            game_id = games.find_one(crosses=ctx.author.id)['game_id']
            await send_embed(ctx, '{} has started a Tic Tac Toe game! Type !accept {} to join.'
                             .format(ctx.author.name, game_id))
        else:
            await send_embed(ctx, 'You are already in a game!')

    @commands.command(hidden=True)
    async def accept(self, ctx, game_id):
        row = games.find_one(game_id=game_id)
        in_game = games.find_one((games.table.c.noughts == ctx.author.id) | (games.table.c.crosses == ctx.author.id))

        if not row:
            await send_embed(ctx, 'Invalid game id, or that game doesn\'t exist.')
            return
        elif ctx.author.id == row['crosses']:
            await send_embed(ctx, 'You cannot join your own game!')
            return
        elif in_game:
            await send_embed(ctx, 'You are already in a game!')
            return
        else:
            games.update(dict(game_id=game_id, noughts=ctx.author.id), ['game_id'])
            await send_embed(ctx, 'You have successfully joined the game! <@{}> type `!place <position>` to start!'
                             .format(row['crosses']))
            ttt_message: Message = await send_embed(ctx, '```'
                                                         '1 | 2 | 3\t\t\t Type !place <position> to play your turn.\n'
                                                         '---------\t\t\t Get three in a row/diagonal to win.\n'
                                                         '4 | 5 | 6\t\t\t It is currently crosses\' turn.\n'
                                                         '---------\t\t\t Type !end to end the game.\n'
                                                         '7 | 8 | 9\n'
                                                         '```')

            games.update(dict(game_id=game_id, message=ttt_message.id), row['game_id'])

    @commands.command(hidden=True)
    async def place(self, ctx, arg):
        row = games.find_one((games.table.c.noughts == ctx.author.id) | (games.table.c.crosses == ctx.author.id))

        if not row:
            await send_embed(ctx, 'You are not in a game! Type `!ttt` to start one.')
            return
        elif not row['message']:
            await send_embed(ctx, 'The game hasn\'t started yet!')
            return
        elif row[row['turn']] != ctx.author.id:
            await send_embed(ctx, 'It is not your turn.')
            return
        elif arg not in [str(i) for i in range(1, 10)]:
            await send_embed(ctx, 'Invalid argument, type a number from 1 - 9')
            return

        cmd = await ctx.fetch_message(ctx.message.id)
        await cmd.delete()

        symbol = "X" if row['turn'] == 'crosses' else "O"
        positions = games.find_one(game_id=row['game_id'])['positions']
        p = json.loads(positions)
        if p[arg] == "X" or p[arg] == "O":
            await send_embed(ctx, 'That spot is already taken!')
            return
        else:
            p[arg] = symbol
        p = json.dumps(p)
        games.update(dict(game_id=row['game_id'], positions=p), ['game_id'])

        positions = games.find_one(game_id=row['game_id'])['positions']
        p = json.loads(positions)

        def end_game():
            games.delete(game_id=row['game_id'])

        msg = await ctx.fetch_message(row['message'])
        await msg.edit(embed=Embed(
            description='```'
                        '{0} | {1} | {2}\t\t\t Type !place <position> to play your turn\n'
                        '---------\t\t\t Get three in a row/diagonal to win.\n'
                        '{3} | {4} | {5}\t\t\t It is currently {9}\' turn.\n'
                        '---------\n'
                        '{6} | {7} | {8}\n'
                        '```'.format(p["1"], p["2"], p["3"], p["4"], p["5"],
                                     p["6"], p["7"], p["8"], p["9"], row['turn'])))

        for h in [p["1"] + p["2"] + p["3"],
                  p["4"] + p["5"] + p["6"],
                  p["7"] + p["8"] + p["9"]]:
            if h == "XXX":
                await send_embed(ctx, "<@{}> has won on Rows!".format(row['crosses']))
                end_game()
                return
            elif h == "OOO":
                await send_embed(ctx, "<@{}> has won on Rows!".format(row['noughts']))
                end_game()
                return

        for v in [p["1"] + p["4"] + p["7"],
                  p["2"] + p["5"] + p["8"],
                  p["3"] + p["6"] + p["9"]]:
            if v == "XXX":
                await send_embed(ctx, "<@{}> has won on Columns!".format(row['crosses']))
                end_game()
                return
            elif v == "OOO":
                await send_embed(ctx, "<@{}> has won on Columns!".format(row['noughts']))
                end_game()
                return

        for d in [p["1"] + p["5"] + p["9"],
                  p["3"] + p["5"] + p["7"]]:
            if d == "XXX":
                await send_embed(ctx, "<@{}> has won on Diagonals!".format(row['crosses']))
                end_game()
                return
            elif d == "OOO":
                await send_embed(ctx, "<@{}> has won on Diagonals!".format(row['noughts']))
                end_game()
                return

        if " " not in p.values():
            await send_embed(ctx, "It ended in a tie!")
            end_game()
            return

        next_turn = 'noughts' if row['turn'] == 'crosses' else 'crosses'
        games.update(dict(game_id=row['game_id'], turn=next_turn), ['game_id'])

    @commands.command(hidden=True)
    async def end(self, ctx):
        row = games.find_one((games.table.c.noughts == ctx.author.id) | (games.table.c.crosses == ctx.author.id))

        if not row:
            await send_embed(ctx, 'You are not in a game! Type `!ttt` to start one.')
        else:
            games.delete(game_id=row['game_id'])
            await send_embed(ctx, '{} has ended the game.'.format(ctx.author.name))


for c in [Miscellaneous, Economy, Games]:
    bot.add_cog(c(bot))

bot.run(config['token'])
db.close()
