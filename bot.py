import discord
from discord.ext import commands, tasks
from datetime import date, datetime, timedelta
import pickle
from os import path
import asyncio
import re

cmdPrefix = "!"
tokenKey = "NzU0Nzk1MzA4NzIxODk3NDky.X1576Q.puMLg79Y-DNpFGtjiCHVRdf9Stg"
bot = commands.Bot(command_prefix=cmdPrefix, description="")


print("Initiating...")
server = None
prod_channel = None
txt_channel = None
loaded = False
midnight_loop_running = False
offset = timedelta(hours=2)
class User:
    def __init__(self, userId):
        self.userId = userId
        self.days = dict()

    def add_task(self, task_obj):
        if date.today() in self.days:
            self.days[date.today()].append(task_obj)
            # TODO: add more values for each task (e.g. points, type)
        else:
            self.days[date.today()] = [task_obj]

    def today_hours(self, category=None, name=None):
        hours = timedelta()
        if date.today() in self.days:
            for task in self.days[date.today()]:
                if category is not None and task["category"] != category:
                    continue
                if name is not None and task["name"] != name:
                    continue
                hours += task["end"] - task["start"]
            if hours.total_seconds() != 0: # prevent division by zero error
                return round(hours.total_seconds() / 3600, 2)
            else:
                return 0
        else:
            return 0

    def week_hours(self, category=None, name=None):
        hours = timedelta()
        for delta in range(7):
            if (date.today() - timedelta(days=delta)) in self.days:
                for task in self.days[date.today() - timedelta(days=delta)]:
                    if category is not None and task["category"] != category:
                        continue
                    if name is not None and task["name"] != name:
                        continue
                    hours += task["end"] - task["start"]
        return round(hours.total_seconds() / 3600, 2)

    def month_hours(self, category=None, name=None):
        hours = timedelta()
        for delta in range(date.today().day):
            if (date.today() - timedelta(days=delta)) in self.days:
                for task in self.days[date.today() - timedelta(days=delta)]:
                    if category is not None and task["category"] != category:
                        continue
                    if name is not None and task["name"] != name:
                        continue
                    hours += task["end"] - task["start"]
        return round(hours.total_seconds() / 3600, 2)
    # TODO: Generate a graph for a given date :D


# Store the information in a dictionary: ['id']: (time started, length, description)
data_store = dict()  # Store the current users in a set

current_users = dict()  # ['id']: [task name, category, start, end]

last_online = datetime.now()  # Stored as a datetime

outage_intervals = []  # Stored in tuples, [(start, end)]

queue = dict()  # Stored as dict ['id']: (task name, category, end time)

reminder_queue = dict() # Stored as dict ['id']: task object

async def notify(userId, eta):
    await asyncio.sleep(max(0,(eta - datetime.now()).total_seconds()))
    usr = server.get_member(userId)
    await txt_channel.send("{0}, 2 hours have passed. Please update your task!".format(usr.mention))
    await usr.move_to(None)

@tasks.loop(seconds=5)
async def save_loop():
    # update last_online, update current_users
    if loaded:
        # print("saved")
        last_online = datetime.now()
        with open("data.pickle", "wb") as handle:
            pickle.dump(data_store, handle)
            pickle.dump(last_online, handle)
            pickle.dump(current_users, handle)
            pickle.dump(outage_intervals, handle)
            pickle.dump(queue, handle)


@tasks.loop(hours=24)
async def my_loop():
    global midnight_loop_running
    print("midnight loop starting")
    midnight_loop_running = True
    now = datetime.now()
    next = now + timedelta(hours=24)
    # Do the normal tasks
    # Iterate through current_users, set tasks, create new ones
    for userId, task in current_users.items():
        oldTask = task
        oldTask["end"] = now.replace(hour=0, minute=0, second=0, microsecond=0)
        data_store[userId].add_task(oldTask)
        newTask = {
            "category": task["category"],
            "name": task["name"],
            "start": oldTask["end"],
            "end": task["end"]
        }
        current_users[userId] = newTask
    now = datetime.now()
    interval = next - now
    print("waiting for " + str(interval.total_seconds()) + " seconds")
    my_loop.change_interval(seconds=interval.total_seconds())
    midnight_loop_running = False


@my_loop.before_loop
async def my_loop_before():
    now = datetime.now()
    next = datetime.now()

    next = next.replace(hour=0, minute=0, second=0, microsecond=1000)
    if next < now:
        next = next.replace(day=now.day + 1)
    print(next)
    print("waiting for " + str((next - now).total_seconds()) + " seconds")
    await asyncio.sleep((next - now).total_seconds())

@bot.event
async def on_ready():
    global server, prod_channel, txt_channel, data_store, last_online, current_users, outage_intervals, queue, loaded, reminder_queue
    print("Logged in as " + bot.user.name)
    print(bot.user.id)
    print("Command prefix: " + repr(cmdPrefix))
    print("--")
    server = bot.get_guild(732687478003204097)
    if server is None:
        print("server is none")
    prod_channel = bot.get_channel(754869911225892915)
    if prod_channel is None:
        print("prod channel is none")
    txt_channel = bot.get_channel(755205065282945085)
    if txt_channel is None:
        print("txt_channel is none")
    # Load all values in data_store
    if not path.exists("data.pickle"):
        loaded = True
        return
    with open("data.pickle", "rb") as handle:
        data_store = pickle.load(handle)
        last_online = pickle.load(handle)
        current_users = pickle.load(handle)
        outage_intervals = pickle.load(handle)
        queue = pickle.load(handle)

    # Log outage into entry
    outage_intervals.append((last_online, datetime.now()))
    # Get current members in vc
    channel_members = prod_channel.voice_states
    # Iterate through the ids in data_store, check if they are still valid
    deletion_list = []
    for userId, task in current_users.items():
        plr = data_store[userId]
        oldTask = task
        oldTask["end"] = last_online
        plr.add_task(oldTask)
        # check if player is still in voice channel
        if userId in channel_members:
            if (task["end"] - datetime.now()).total_seconds() < 0:
                deletion_list.append(userId)
            else:
                newTask = {
                    "name": task["name"],
                    "category": task["category"],
                    "start": datetime.now(),
                    "end": datetime.now() + offset
                }
                reminder_queue[userId] = asyncio.create_task(notify(userId, task["end"]))
                await reminder_queue[userId]
                # TODO: create new reminder object
                current_users[userId] = newTask
    for id in deletion_list:
        del current_users[id]
    # Iterate through current users in vc, check if they have logged. current_members is now up to date.
    for userId, voiceState in channel_members.items():
        if userId not in current_users:
            await txt_channel.send('{0}, you must first log a task before joining the voice channel.'.format(
                server.get_member(userId).mention))
            try:
                await server.get_member(userId).move_to(None)
            except:
                pass
    loaded = True


@bot.command()
async def ping(ctx):
    await ctx.send("Pong: {0} ms".format(round(bot.latency * 1000, 1)))


@bot.command()
async def log(ctx, *args):
    if midnight_loop_running:
        await ctx.send("Try again in a few seconds, currently busy...")
        return
    # Check if user is already in vc
    description = ' '.join(args)
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
        await ctx.send("Your profile has been saved in the database.")
    await ctx.send("Please enter a category.")
    def check(m):
        return m.channel == ctx.channel and m.author.id == ctx.author.id
    try:
        category = (await bot.wait_for('message', check=check, timeout=15.0)).content
    except asyncio.TimeoutError:
        await ctx.send("You've been timed out. Try again later.")
        return
    if category.startswith("!"):
        await ctx.send("Invalid category.")
        return
    if ctx.author.id in prod_channel.voice_states:
        plr = data_store[ctx.author.id]
        oldTask = {
            "category": current_users[ctx.author.id]["category"],
            "name": current_users[ctx.author.id]["name"],
            "start": current_users[ctx.author.id]["start"],
            "end": datetime.now()
        }
        newTask = {
            "category": category,
            "name": description,
            "start": datetime.now(),
            "end": datetime.now() + offset
        }
        plr.add_task(oldTask)
        current_users[ctx.author.id] = newTask
        # Cancel old reminder
        reminder_queue[ctx.author.id].cancel()
        # Create new reminder
        reminder_queue[ctx.author.id] = asyncio.create_task(notify(ctx.author.id, newTask["end"]))

        await ctx.send("Success {0}! Your task has been changed to `{1}` in the category `{2}` for the next 2 hours.".format(ctx.author.mention, description, category))

        # queue[ctx.author.id] = [description, ]
    else:
        queue[ctx.author.id] = {
            "category": category,
            "name": description,
            "end": datetime.now() + offset
        }
        await ctx.send(
            "Success {0}! Your task has been set to `{1}` in the category `{2}` for the next 2 hours. Join the voice call to start logging your hours.".format(
                ctx.author.mention,
                description, category))


@bot.command()
async def daily(ctx):
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
    category = re.match(r'category="[^"]*"', ctx.message.content)
    name = re.match(r'desc="[^"]*"', ctx.message.content)
    if category is not None:
        category = category.group()[10:-1]
    if name is not None:
        name = name.group()[5:-1]
    await ctx.send("Your study time for today is " + str(data_store[ctx.author.id].today_hours(category, name)) + " hours.")


@bot.command()
async def weekly(ctx):
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
    category = re.match(r'category="[^"]*"', ctx.message.content)
    name = re.match(r'desc="[^"]*"', ctx.message.content)
    if category is not None:
        category = category.group()[10:-1]
    if name is not None:
        name = name.group()[5:-1]
    await ctx.send("Your study time for this week is " + str(data_store[ctx.author.id].week_hours(category, name)) + " hours.")


@bot.command()
async def monthly(ctx):
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
    category = re.match(r'category="[^"]*"', ctx.message.content)
    name = re.match(r'desc="[^"]*"', ctx.message.content)
    if category is not None:
        category = category.group()[10:-1]
    if name is not None:
        name = name.group()[5:-1]
    await ctx.send("Your study time for this month is " + str(data_store[ctx.author.id].month_hours(category, name)) + " hours.")


@bot.command()
async def profile(ctx):
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
    await ctx.send(str(data_store[ctx.author.id].days))


@bot.event
async def on_voice_state_update(member, before, after):
    # Check if it's relevant:
    if (before.channel == prod_channel) or (after.channel == prod_channel):
        # First check if member was in current_members (should be)
        # member joins prod-channel from somewhere else
        if after.channel == prod_channel and before.channel != prod_channel:
            # member joined prod-channel
            # check if member is in queue
            if member.id in queue and (queue[member.id]["end"] - datetime.now()).total_seconds() > 0:
                # add member to current_members, send confirmation message
                current_users[member.id] = {
                    "category": queue[member.id]["category"],
                    "name": queue[member.id]["name"],
                    "start": datetime.now(),
                    "end": datetime.now() + offset
                }
                reminder_queue[member.id] = asyncio.create_task(notify(member.id, queue[member.id]["end"]))
                del queue[member.id]
                await txt_channel.send('{0}, you are verified. Begin studying!'.format(member.mention))
            else:
                if member.id in queue:
                    del queue[member.id]
                # member is not authorized
                await txt_channel.send('{0}, you must first log a task before joining the voice channel.'.format(
                    member.mention))
                try:
                    await member.move_to(None)
                except:
                    pass
        # member leaves prod-channel
        elif after.channel != prod_channel and before.channel == prod_channel:
            if member.id in queue:
                del queue[member.id]
            if member.id in current_users:
                # log member data
                task = current_users[member.id]
                oldTask = {
                    "category": task["category"],
                    "name": task["name"],
                    "start": task["start"],
                    "end": datetime.now()
                }
                data_store[member.id].add_task(oldTask)
                del current_users[member.id]
                if member.id in reminder_queue:
                    reminder_queue[member.id].cancel()
                    del reminder_queue[member.id]
                await txt_channel.send('{0}, your hours have been logged.'.format(member.mention))


save_loop.start()
my_loop.start()
bot.run(tokenKey)
