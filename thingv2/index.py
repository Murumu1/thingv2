from discord.ext import commands
import random
import sqlite3

import json

with open('config.json') as f:
    config = json.load(f)

bot = commands.Bot(command_prefix='!')

db = sqlite3.connect('economy')
cursor = db.cursor()


@bot.event
async def on_ready():
    print('Logged on as', bot.user)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)


# @bot.event
# async def on_command_error(ctx, error):
#     error = getattr(error, 'original', error)
#
#     if isinstance(error, commands.UserInputError):
#         await ctx.send("Missing argument: " + ctx.command.usage)
#         print(error)


class Miscellaneous(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command()
    async def say(self, ctx, *, arg):
        await ctx.send(arg)

    @commands.command()
    async def roll(self, ctx):
        await ctx.send('You rolled {}'.format(random.randint(1, 6)))


class Economy(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(brief="Access your bank account!",
                      aliases=["balance", "account"],
                      help="Used to check your balance. Shows the amount of money you currently own.")
    async def bal(self, ctx):
        cursor.execute('SELECT * FROM users WHERE id = {}'.format(ctx.author.id))
        row = cursor.fetchone()

        if not row:
            cursor.execute('''INSERT INTO users(id, nick, balance) 
            VALUES ({}, '{}', {})'''.format(ctx.author.id, ctx.author.name, 0))
            db.commit()

            await ctx.send('I have set up your account!\nBalance: ${}'.format(0))
            return
        else:
            await ctx.send('Balance: ${}'.format(row[2]))

    @commands.command(aliases=["add", "add_money"],
                      hidden=True)
    async def gain(self, ctx, amount):
        cursor.execute('SELECT * FROM users WHERE id = {}'.format(ctx.author.id))
        row = cursor.fetchone()

        if not row:
            await ctx.send('Type !bal to set up your account!')
            return
        else:
            new_bal = row[2] + int(amount)
            cursor.execute('UPDATE users SET balance = {} WHERE id = {}'.format(new_bal, ctx.author.id))
            db.commit()

            await ctx.send(
                '{}, I have added ${} to your account\nnew bal: ${}'.format(ctx.author.name, amount, new_bal))

    @commands.command(brief="Gamble your money!",
                      usage="<amount>",
                      help="Put your money on the line in hopes to double the amount you enter. "
                           "A roll over 50 (excluding) is a win")
    async def gamble(self, ctx, amount):
        cursor.execute('SELECT * FROM users WHERE id = {}'.format(ctx.author.id))
        row = cursor.fetchone()

        if not row:
            await ctx.send('Type !bal to set up your account!')
            return
        elif int(amount) > row[2]:
            await ctx.send('You cannot gamble more than you have.\nBalance: ${}'.format(row[2]))
            return
        elif int(amount) < 5:
            await ctx.send('Minimum bet is $5')
            return
        else:
            num = random.randint(1, 100)
            new_bal = row[2]
            if num <= 50:
                new_bal -= int(amount)
                msg = 'Unfortunately you rolled {}. You lost ${}'.format(num, amount)
            else:
                new_bal += int(amount)
                msg = 'Congrats! you rolled {}. You won ${}'.format(num, amount)

            cursor.execute('UPDATE users SET balance = {} WHERE id = {}'.format(new_bal, ctx.author.id))
            db.commit()
            await ctx.send('{}\nBalance: ${}'.format(msg, new_bal))


class Games(commands.Cog):
    def __init__(self, client):
        self.bot = client

    @commands.command(brief="Play a game of Tic Tac Toe!",
                      help="Starts a Tic Tac Toe game, use !accept <gameid> to accept a game, "
                           "then to put a cross/nought use !place <position> and use !end to end "
                           "the game if needed.",
                      aliases=["tictactoe"])
    async def ttt(self, ctx):
        cursor.execute('SELECT * FROM ttt_games WHERE noughts = {0} OR crosses = {0}'.format(ctx.author.id))
        row = cursor.fetchone()

        if not row:
            cursor.execute('INSERT INTO ttt_games(crosses) VALUES ({})'.format(ctx.author.id))
            db.commit()

            cursor.execute('SELECT game_id FROM ttt_games WHERE crosses = {}'.format(ctx.author.id))
            game_id = cursor.fetchone()[0]
            await ctx.send('{} has started a Tic Tac Toe game! Type !accept {} to join.'.format(ctx.author.name, game_id))
        else:
            await ctx.send('You are already in a game!')

    @commands.command(hidden=True)
    async def accept(self, ctx, game_id):
        cursor.execute('SELECT * FROM ttt_games WHERE game_id = {}'.format(game_id))
        row = cursor.fetchone()

        cursor.execute('SELECT * FROM ttt_games WHERE noughts = {0} OR crosses = {0}'.format(ctx.author.id))
        in_game = cursor.fetchone()

        if not row:
            await ctx.send('Invalid game id, or that game doesn\'t exist.')
            return
        elif ctx.author.id == row[2]:
            await ctx.send('You cannot join your own game!')
            return
        elif in_game:
            await ctx.send('You are already in a game!')
            return
        else:
            cursor.execute('UPDATE ttt_games SET noughts = {} WHERE game_id = {}'.format(ctx.author.id, game_id))
            db.commit()
            await ctx.send('You have successfully joined the game! <@{}> type `!place <position>` to start!'
                           .format(row[2]))
            ttt_message = await ctx.send('```'
                                         '1 | 2 | 3\t\t\t Type !place <position> to play your turn.\n'
                                         '---------\t\t\t Get three in a row/diagonal to win.\n'
                                         '4 | 5 | 6\t\t\t It is currently crosses\' turn.\n'
                                         '---------\t\t\t Type !end to end the game.\n'
                                         '7 | 8 | 9\n'
                                         '```')

            cursor.execute('UPDATE ttt_games SET message = {} WHERE game_id = {}'.format(ttt_message.id, row[0]))

    @commands.command(hidden=True)
    async def place(self, ctx, arg):
        cursor.execute('SELECT * FROM ttt_games WHERE noughts = {0} OR crosses = {0}'.format(ctx.author.id))
        game = cursor.fetchone()

        if not game:
            await ctx.send('You are not in a game! Type `!ttt` to start one.')
            return
        elif not game[5]:
            await ctx.send('The game hasn\'t started yet!')
            return
        elif game[game[3]] != ctx.author.id:
            await ctx.send('It is not your turn.')
            return
        elif arg not in [str(i) for i in range(1, 10)]:
            await ctx.send('Invalid argument, type a number from 1 - 9')
            return

        cmd = await ctx.fetch_message(ctx.message.id)
        await cmd.delete()

        symbol = "X" if game[3] == 2 else "O"
        cursor.execute('SELECT positions FROM ttt_games WHERE game_id = {}'.format(game[0]))
        r = cursor.fetchone()[0]
        p = json.loads(r)
        if p[arg] == "X" or p[arg] == "O":
            await ctx.send('That spot is already taken!')
            return
        else:
            p[arg] = symbol
        p = json.dumps(p)
        cursor.execute("UPDATE ttt_games SET positions = '{}' WHERE game_id = {}".format(p, game[0]))
        db.commit()

        cursor.execute('SELECT positions FROM ttt_games WHERE game_id = {}'.format(game[0]))
        r = cursor.fetchone()[0]
        p = json.loads(r)

        def end_game():
            cursor.execute('DELETE FROM ttt_games WHERE game_id = {}'.format(game[0]))
            db.commit()

        msg = await ctx.fetch_message(game[5])
        await msg.edit(content='```'
                               '{0} | {1} | {2}\t\t\t Type !place <position> to play your turn\n'
                               '---------\t\t\t Get three in a row/diagonal to win.\n'
                               '{3} | {4} | {5}\t\t\t It is currently {9}\' turn.\n'
                               '---------\n'
                               '{6} | {7} | {8}\n'
                               '```'.format(p["1"], p["2"], p["3"], p["4"], p["5"],
                                            p["6"], p["7"], p["8"], p["9"],
                                            ("crosses" if game[3] == 1 else "noughts")))

        for h in [p["1"] + p["2"] + p["3"],
                  p["4"] + p["5"] + p["6"],
                  p["7"] + p["8"] + p["9"]]:
            if h == "XXX":
                await ctx.send("<@{}> has won on Rows!".format(game[2]))
                end_game()
                return
            elif h == "OOO":
                await ctx.send("<@{}> has won on Rows!".format(game[1]))
                end_game()
                return

        for v in [p["1"] + p["4"] + p["7"],
                  p["2"] + p["5"] + p["8"],
                  p["3"] + p["6"] + p["9"]]:
            if v == "XXX":
                await ctx.send("<@{}> has won on Columns!".format(game[2]))
                end_game()
                return
            elif v == "OOO":
                await ctx.send("<@{}> has won on Columns!".format(game[1]))
                end_game()
                return

        for d in [p["1"] + p["5"] + p["9"],
                  p["3"] + p["5"] + p["7"]]:
            if d == "XXX":
                await ctx.send("<@{}> has won on Diagonals!".format(game[2]))
                end_game()
                return
            elif d == "OOO":
                await ctx.send("<@{}> has won on Diagonals!".format(game[1]))
                end_game()
                return

        if " " not in p.values():
            await ctx.send("It ended in a tie!")
            end_game()
            return

        next_turn = 1 if game[3] == 2 else 2
        cursor.execute('UPDATE ttt_games SET turn = {} WHERE game_id = {}'.format(next_turn, game[0]))
        db.commit()

    @commands.command(hidden=True)
    async def end(self, ctx):
        cursor.execute('SELECT * FROM ttt_games WHERE noughts = {0} OR crosses = {0}'.format(ctx.author.id))
        game = cursor.fetchone()

        if not game:
            await ctx.send('You are not in a game! Type `!ttt` to start one.')
        else:
            cursor.execute('DELETE FROM ttt_games WHERE game_id = {}'.format(game[0]))
            db.commit()
            await ctx.send('{} has ended the game.'.format(ctx.author.name))


for c in [Miscellaneous, Economy, Games]:
    bot.add_cog(c(bot))

bot.run(config['token'])
db.close()
