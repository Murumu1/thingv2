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

    @commands.command()
    async def bal(self, ctx):
        cursor.execute('SELECT * FROM users WHERE id = {}'.format(ctx.author.id))
        row = cursor.fetchone()

        if not row:
            cursor.execute('''INSERT INTO users(id, nick, balance) 
            VALUES ({}, '{}', {})'''.format(ctx.author.id, ctx.author.name, 0))
            db.commit()

            await ctx.send('I have set up your account!\nBalance: ${}'.format(0))
        else:
            await ctx.send('Balance: ${}'.format(row[2]))

    @commands.command()
    async def gain(self, ctx, arg):
        cursor.execute('SELECT * FROM users WHERE id = {}'.format(ctx.author.id))
        row = cursor.fetchone()

        if not row:
            await ctx.send('Type !bal to set up your account!')
        else:
            new_bal = row[2] + int(arg)
            cursor.execute('UPDATE users SET balance = {} WHERE id = {}'.format(new_bal, ctx.author.id))
            db.commit()

            await ctx.send('{}, I have added ${} to your account\nnew bal: ${}'.format(ctx.author.name, arg, new_bal))

    @commands.command()
    async def gamble(self, ctx, arg):
        cursor.execute('SELECT * FROM users WHERE id = {}'.format(ctx.author.id))
        row = cursor.fetchone()

        if not row:
            await ctx.send('Type !bal to set up your account!')
        elif int(arg) > row[2]:
            await ctx.send('You cannot gamble more than you have.\nBalance: ${}'.format(row[2]))
        else:
            num = random.randint(1, 100)
            new_bal = row[2]
            if num <= 50:
                new_bal -= int(arg)
                msg = 'Unfortunately you rolled {}. You lost ${}'.format(num, arg)
            else:
                new_bal += int(arg)
                msg = 'Congrats! you rolled {}. You won ${}'.format(num, arg)

            cursor.execute('UPDATE users SET balance = {} WHERE id = {}'.format(new_bal, ctx.author.id))
            db.commit()
            await ctx.send('{}\nBalance: ${}'.format(msg, new_bal))


for c in [Miscellaneous, Economy]:
    bot.add_cog(c(bot))

bot.run(config['token'])
db.close()
