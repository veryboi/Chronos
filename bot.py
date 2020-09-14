import discord
from discord.ext import commands, tasks
import sched, time
from datetime import date, datetime, timedelta
import pickle
from os import path

cmdPrefix = "!"
tokenKey = "NzU0Nzk1MzA4NzIxODk3NDky.X1576Q.puMLg79Y-DNpFGtjiCHVRdf9Stg"
bot = commands.Bot(command_prefix=cmdPrefix, description="")


print("Initiating...")
server = None
prod_channel = None
txt_channel = None
loaded = False


class User:
    def __init__(self, userId):
        self.userId = userId
        self.days = dict()

    def add_task(self, taskName, start, end):
        if date.today() in self.days:
            self.days[date.today()].append([taskName, start, end])
            # TODO: add more values for each task (e.g. points, type)
        else:
            self.days[date.today()] = [[taskName, start, end]]

    def today_hours(self):
        hours = timedelta()
        if date.today() in self.days:
            for task in self.days[date.today()]:
                hours += task[2] - task[1]
            if hours.total_seconds() != 0: # prevent division by zero error
                return round(hours.total_seconds() / 3600, 2)
            else:
                return 0
        else:
            return 0

    def week_hours(self):
        hours = timedelta()
        for delta in range(7):
            if (date.today() - timedelta(days=delta)) in self.days:
                for task in self.days[date.today() - timedelta(days=delta)]:
                    hours += task[2] - task[1]
        return round(hours.total_seconds() / 3600, 2)

    def month_hours(self):
        hours = timedelta()
        for delta in range(date.today().day):
            if (date.today() - timedelta(days=delta)) in self.days:
                for task in self.days[date.today() - timedelta(days=delta)]:
                    hours += task[2] - task[1]
        return round(hours.total_seconds() / 3600, 2)
    # TODO: Generate a graph for a given date :D


s = sched.scheduler(time.perf_counter,time.sleep)

# Store the information in a dictionary: ['id']: (time started, length, description)
data_store = dict()  # Store the current users in a set

current_users = dict()  # ['id']: [task name, start, end]

last_online = datetime.now()  # Stored as a datetime

outage_intervals = []  # Stored in tuples, [(start, end)]

queue = dict()  # Stored as dict ['id']: (task name, end time)


@tasks.loop(seconds=5)
async def save_loop():
    # update last_online, update current_users
    if loaded:
        last_online = datetime.now()
        with open("data.pickle", "wb") as handle:
            pickle.dump(data_store, handle)
            pickle.dump(last_online, handle)
            pickle.dump(current_users, handle)
            pickle.dump(outage_intervals, handle)
            pickle.dump(queue, handle)


@bot.event
async def on_ready():
    global server, prod_channel, txt_channel, data_store, last_online, current_users, outage_intervals, queue, loaded
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
    txt_channel = bot.get_channel(732687478426959976)
    if txt_channel is None:
        print("txt_channel is none")
    # Load all values in data_store
    if not path.exists("data.pickle"):
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
        plr.add_task(task[0], task[1], last_online)
        # check if player is still in voice channel
        if userId in channel_members:
            if (task[2] - datetime.now()).total_seconds() < 0:
                deletion_list.append(userId)
            else:
                current_users[userId] = [task[0], datetime.now(), task[2]]
    for id in deletion_list:
        del current_users[id]
    # Iterate through current users in vc, check if they have logged. current_members is now up to date.
    for userId, voiceState in channel_members.items():
        if userId not in current_users:
            await txt_channel.send('{0}, you must first log a task before joining the voice channel!'.format(
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
async def begin(ctx, *args):
    # Check if user is already in vc
    description = ' '.join(args)
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
        await ctx.send("Your profile has been saved in the database!")
    if ctx.author.id in prod_channel.voice_states:
        plr = data_store[ctx.author.id]
        plr.add_task(current_users[ctx.author.id][0], current_users[ctx.author.id][1], datetime.now())
        current_users[ctx.author.id] = [description, datetime.now(), datetime.now() + timedelta(hours=2)]
        await ctx.send("Success {0}! Your task has been changed to `{1}` for the next 2 hours!".format(ctx.author.mention, description))

        # queue[ctx.author.id] = [description, ]
    else:
        queue[ctx.author.id] = [description, datetime.now() + timedelta(hours=2)]
        await ctx.send(
            "Success {0}! Your task has been set to `{1}` for the next 2 hours! Join the voice call to start logging your hours.".format(
                ctx.author.mention,
                description))


@bot.command()
async def daily(ctx):
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
    await ctx.send("Your study time for today is " + str(data_store[ctx.author.id].today_hours()) + " hours.")


@bot.command()
async def weekly(ctx):
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
    await ctx.send("Your study time for this week is " + str(data_store[ctx.author.id].week_hours()) + " hours.")


@bot.command()
async def monthly(ctx):
    if ctx.author.id not in data_store:
        data_store[ctx.author.id] = User(ctx.author.id)
    await ctx.send("Your study time for this month is " + str(data_store[ctx.author.id].month_hours()) + " hours.")


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
            if member.id in queue:
                # add member to current_members, send confirmation message
                current_users[member.id] = [queue[member.id][0], datetime.now(), queue[member.id][1]]
                del queue[member.id]
                await txt_channel.send('{0}, you are verified! Begin studying!'.format(member.mention))
            else:
                # member is not authorized
                await txt_channel.send('{0}, you must first log a task before joining the voice channel!'.format(
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
                data_store[member.id].add_task(task[0], task[1], datetime.now())
                del current_users[member.id]
                await txt_channel.send('{0}, your hours have been logged!'.format(member.mention))


save_loop.start()
bot.run(tokenKey)
