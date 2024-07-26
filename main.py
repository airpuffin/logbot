import discord
from discord.ext import commands, tasks
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
import pytz
import re
import setproctitle
import os

###========== Set process name ==========###

# Get the name of the folder containing the script
script_folder = os.path.basename(os.path.dirname(os.path.realpath(__file__)))

# Set the process title to the folder name
setproctitle.setproctitle(script_folder)

###========== Configuration ==========###
# Load configuration
with open('config.json') as config_file:
    config = json.load(config_file)

DISCORD_TOKEN = config['DISCORD_TOKEN']
LOG_CHANNEL_ID = int(config['LOG_CHANNEL'])
EMBED_COLOR = int(config['EMBED_COLOR'].strip('#'), 16)
HEARTBEAT_SEC = config['HEARTBEAT_SEC']
LOG_FILE = config['LOG_FILE']
MAX_LOG_SIZE = config['MAX_LOG_SIZE']  # Max size in bytes, e.g., 5MB
BACKUP_COUNT = config['BACKUP_COUNT']  # Number of backup files to keep

###========== Logging Setup ==========###
# Set up logging with rotation
utc_tz = timezone.utc
cst_tz = pytz.timezone('America/Chicago')

class CSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        utc_time = datetime.fromtimestamp(record.created, tz=utc_tz)
        cst_time = utc_time.astimezone(cst_tz)
        utc_time_str = utc_time.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        cst_time_str = cst_time.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        return f"{utc_time_str}:INFO: DTG {cst_time_str} -"

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Use RotatingFileHandler
file_handler = RotatingFileHandler(
    LOG_FILE, 
    maxBytes=MAX_LOG_SIZE,  # Max file size before rotating
    backupCount=BACKUP_COUNT  # Number of backup files to keep
)
formatter = CSTFormatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

###========== Bot Setup ==========###
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.reactions = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
logs = []

###========== Event Handlers ==========###
@bot.event
async def on_ready():
    logger.info('Bot has started and is ready.')
    print(f'Logged in as {bot.user.name}')
    bot.log_channel = bot.get_channel(LOG_CHANNEL_ID)
    # heartbeat.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    log_entry = {
        'type': 'message',
        'author_id': message.author.id,
        'author': str(message.author),
        'message_id': message.id,
        'content': message.content,
        'timestamp': datetime.utcnow().isoformat(),
        'channel': str(message.channel)
    }
    logs.append(log_entry)
    log_msg = (f"Message from {log_entry['author']} (ID: {log_entry['author_id']}, "
               f"Message ID: {log_entry['message_id']}): {log_entry['content']}")
    logger.info(log_msg)
    if bot.log_channel:
        embed = discord.Embed(title='Message Logged', description=log_msg, color=EMBED_COLOR)
        await bot.log_channel.send(embed=embed)
    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return

    log_entry = {
        'type': 'message_edit',
        'author_id': before.author.id,
        'author': str(before.author),
        'message_id': before.id,
        'content_before': before.content,
        'content_after': after.content,
        'timestamp': datetime.utcnow().isoformat(),
        'channel': str(before.channel)
    }
    logs.append(log_entry)
    log_msg = (f"Message edited by {log_entry['author']} (ID: {log_entry['author_id']}, "
               f"Message ID: {log_entry['message_id']}): {log_entry['content_before']} -> {log_entry['content_after']}")
    logger.info(log_msg)
    if bot.log_channel:
        embed = discord.Embed(title='Message Edited', description=log_msg, color=EMBED_COLOR)
        await bot.log_channel.send(embed=embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return

    log_entry = {
        'type': 'message_delete',
        'author_id': message.author.id,
        'author': str(message.author),
        'message_id': message.id,
        'content': message.content,
        'timestamp': datetime.utcnow().isoformat(),
        'channel': str(message.channel)
    }
    logs.append(log_entry)
    log_msg = (f"Message deleted from {log_entry['author']} (ID: {log_entry['author_id']}, "
               f"Message ID: {log_entry['message_id']}): {log_entry['content']}")
    logger.info(log_msg)
    if bot.log_channel:
        embed = discord.Embed(title='Message Deleted', description=log_msg, color=EMBED_COLOR)
        await bot.log_channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    log_entry = {
        'type': 'member_join',
        'user_id': member.id,
        'user': str(member),
        'timestamp': datetime.utcnow().isoformat()
    }
    logs.append(log_entry)
    log_msg = f"Member joined: {log_entry['user']} (ID: {log_entry['user_id']})"
    logger.info(log_msg)
    if bot.log_channel:
        embed = discord.Embed(title='Member Joined', description=log_msg, color=EMBED_COLOR)
        await bot.log_channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    log_entry = {
        'type': 'member_remove',
        'user_id': member.id,
        'user': str(member),
        'timestamp': datetime.utcnow().isoformat()
    }
    logs.append(log_entry)
    log_msg = f"Member left: {log_entry['user']} (ID: {log_entry['user_id']})"
    logger.info(log_msg)
    if bot.log_channel:
        embed = discord.Embed(title='Member Left', description=log_msg, color=EMBED_COLOR)
        await bot.log_channel.send(embed=embed)

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        log_entry = {
            'type': 'voice_join',
            'user_id': member.id,
            'user': str(member),
            'channel': str(after.channel),
            'timestamp': datetime.utcnow().isoformat()
        }
        logs.append(log_entry)
        log_msg = (f"User joined voice channel: {log_entry['user']} (ID: {log_entry['user_id']}) "
                   f"in {log_entry['channel']}")
        logger.info(log_msg)
        if bot.log_channel:
            embed = discord.Embed(title='Voice Channel Join', description=log_msg, color=EMBED_COLOR)
            await bot.log_channel.send(embed=embed)
    elif before.channel is not None and after.channel is None:
        log_entry = {
            'type': 'voice_leave',
            'user_id': member.id,
            'user': str(member),
            'channel': str(before.channel),
            'timestamp': datetime.utcnow().isoformat()
        }
        logs.append(log_entry)
        log_msg = (f"User left voice channel: {log_entry['user']} (ID: {log_entry['user_id']}) "
                   f"from {log_entry['channel']}")
        logger.info(log_msg)
        if bot.log_channel:
            embed = discord.Embed(title='Voice Channel Leave', description=log_msg, color=EMBED_COLOR)
            await bot.log_channel.send(embed=embed)

###========== Commands ==========###
@bot.command()
async def loguser(ctx, user: discord.User, limit: int = 5):
    """Searches the entire log file for a user by username or ID and includes x number of recent results."""
    user_id = user.id
    log_entries = []

    # Read the log file
    try:
        with open(LOG_FILE, 'r') as file:
            lines = file.readlines()
    except Exception as e:
        await ctx.send(f'Error reading log file: {e}')
        return

    # Find log entries related to the user
    for line in lines:
        if str(user_id) in line:
            log_entries.append(line.strip())

    # Sort entries by timestamp (assuming timestamps are at the start of each line)
    log_entries.sort(key=lambda entry: re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', entry).group(), reverse=True)

    # Get the most recent entries
    recent_entries = log_entries[:limit]

    if not recent_entries:
        await ctx.send(f'No logs found for {user}.')
        return

    embed = discord.Embed(title=f'Logs for {user}', color=EMBED_COLOR)
    for entry in recent_entries:
        # Extract data using regex
        timestamp_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', entry)
        level_match = re.search(r':INFO:', entry)
        dtg_match = re.search(r'DTG \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', entry)
        content_match = re.search(r'- (.+)', entry)
        
        # Safeguard against missing matches
        timestamp = timestamp_match.group() if timestamp_match else 'N/A'
        level = level_match.group().strip(':') if level_match else 'N/A'
        dtg = dtg_match.group().replace('DTG ', '') if dtg_match else 'N/A'
        content = content_match.group(1).strip() if content_match else 'N/A'

        # Format log entry
        formatted_entry = (
            f"Timestamp: {timestamp}\n"
            f"Level: {level}\n"
            f"DTG: {dtg}\n"
            f"Content: {content}\n"
        )
        embed.add_field(name='Log Entry', value=formatted_entry, inline=False)
    
    await ctx.send(embed=embed)



@bot.command()
async def logadd(ctx, *, text: str):
    """Adds a custom log entry."""
    log_entry = {
        'type': 'custom_log',
        'content': text,
        'timestamp': datetime.utcnow().isoformat()
    }
    logs.append(log_entry)
    log_msg = f"Custom log entry: {log_entry['content']}"
    logger.info(log_msg)
    if bot.log_channel:
        embed = discord.Embed(title='Custom Log Entry', description=log_msg, color=EMBED_COLOR)
        await bot.log_channel.send(embed=embed)

###========== Heartbeat Task ==========###
# @tasks.loop(seconds=HEARTBEAT_SEC)
# async def heartbeat():
#     utc_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
#     cst_time = datetime.now(cst_tz).strftime('%Y-%m-%d %H:%M:%S')
#     heartbeat_msg = f"Heartbeat: Bot is still alive. UTC Time: {utc_time} CST Time: {cst_time}"
#     logger.info(heartbeat_msg)

###========== Run Bot ==========###
bot.run(DISCORD_TOKEN)
