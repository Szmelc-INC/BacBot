import discord
import os
import asyncio
from collections import defaultdict
from datetime import datetime

# SERVER ID
s_id = SERVER_ID
# BOT TOKEN
bt = 'BOT_TOKEN'


# Define the necessary intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True  # Needed to list all members
intents.bans = True

client = discord.Client(intents=intents)

# Statistics dictionaries
channel_stats = defaultdict(lambda: {'messages': 0, 'attachments': 0})
user_stats = defaultdict(lambda: {'messages': 0, 'attachments': 0})
user_channel_stats = defaultdict(lambda: defaultdict(lambda: {'messages': 0, 'attachments': 0}))

async def download_attachments(message, channel_dir):
    attachment_filenames = []
    for attachment in message.attachments:
        # Generate the filename
        max_filename_length = 255
        name, ext = os.path.splitext(attachment.filename)
        truncated_name = name[:max_filename_length - len(ext) - 1]
        filename = truncated_name + ext

        counter = 1
        file_path = os.path.join(channel_dir, filename)
        while os.path.exists(file_path) and not os.path.isfile(file_path):
            filename = f"{truncated_name}_{counter}{ext}"
            file_path = os.path.join(channel_dir, filename)
            counter += 1

        # Check if file already exists, skip download if it does
        if not os.path.exists(file_path):
            try:
                await attachment.save(file_path)
            except Exception as e:
                print(f"Error saving attachment: {e}")
                continue

            # Update statistics only for new files
            channel_stats[channel_dir]['attachments'] += 1
            user_stats[message.author.display_name]['attachments'] += 1
            user_channel_stats[message.author.display_name][channel_dir]['attachments'] += 1

        attachment_filenames.append(filename)
    
    return attachment_filenames

async def backup_channel(channel, parent_dir):
    print(f"Backing up channel: {channel.name}")
    channel_dir = os.path.join(parent_dir, channel.name)
    os.makedirs(channel_dir, exist_ok=True)

    try:
        with open(os.path.join(channel_dir, f"{channel.name}.txt"), "w") as file:
            # Fetch messages and store them in a list
            messages = [message async for message in channel.history(limit=None)]
            # Reverse the list to get chronological order
            messages.reverse()

            for message in messages:
                attachment_filenames = await download_attachments(message, channel_dir)
                file.write(f"{message.created_at} - {message.author.display_name}: {message.content}")
                if attachment_filenames:
                    file.write(" [Attachments: " + ", ".join(attachment_filenames) + "]")
                file.write("\n")

                # Update statistics
                channel_stats[channel_dir]['messages'] += 1
                user_stats[message.author.display_name]['messages'] += 1
                user_channel_stats[message.author.display_name][channel_dir]['messages'] += 1
    except discord.errors.Forbidden:
        print(f"Skipping channel '{channel.name}': Bot does not have permission to view this channel.")
    except Exception as e:
        print(f"Error processing channel '{channel.name}': {e}")

async def backup_bans(server, backup_dir):
    ban_file_path = os.path.join(backup_dir, "banned.txt")
    with open(ban_file_path, "w") as ban_file:
        try:
            async for ban_entry in server.bans():
                ban_file.write(f"{ban_entry.user.name}#{ban_entry.user.discriminator} - Banned on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        except discord.errors.Forbidden:
            print("Bot does not have permissions to view ban list.")
        except Exception as e:
            print(f"Error retrieving ban list: {e}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

    server_id = s_id  # Replace with your server's ID
    server = client.get_guild(server_id)

    if server is None:
        print("Server not found. Check the server ID.")
        return

    backup_dir = f"server_backup_{server.name}"
    os.makedirs(backup_dir, exist_ok=True)

    main_file_path = os.path.join(backup_dir, "main.txt")

    # Write server info, roles, and members to main.txt
    with open(main_file_path, "w") as main_log:
        main_log.write(f"Server Name: {server.name}\n")
        main_log.write(f"Server Description: {server.description}\n")
        main_log.write("Server Roles:\n")
        for role in server.roles:
            main_log.write(f"{role.name}\n")
        main_log.write("Server Members:\n")
        for member in server.members:
            member_roles = ', '.join([role.name for role in member.roles if role.name != "@everyone"])
            main_log.write(f"{member.name}#{member.discriminator} - Roles: {member_roles}\n")

    # Append backup number and date
    backup_number = 1
    with open(main_file_path, "r") as main_log:
        for line in main_log:
            if line.startswith("backup_"):
                backup_number += 1

    with open(main_file_path, "a") as main_log:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        main_log.write(f"backup_{backup_number}: {current_time}\n")

    # Backup channels and collect statistics
    for channel in server.channels:
        if isinstance(channel, discord.TextChannel):
            await backup_channel(channel, backup_dir)

    # Backup banned users
    await backup_bans(server, backup_dir)

    # Writing main.txt
    with open(main_file_path, "a") as main_log:  # Append mode
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        main_log.write(f"backup_{backup_number}: {current_time}\n")

    # Writing stats.txt
    with open(os.path.join(backup_dir, "stats.txt"), "w") as stats_file:
        stats_file.write("Channel Statistics:\n")
        for channel, stats in channel_stats.items():
            channel_name = channel.split('/')[-1]
            stats_file.write(f"{channel_name}: Messages - {stats['messages']}, Attachments - {stats['attachments']}\n")

        stats_file.write("\nUser Statistics:\n")
        for user, stats in user_stats.items():
            stats_file.write(f"{user}: Messages - {stats['messages']}, Attachments - {stats['attachments']}\n")

        stats_file.write("\nUser-Channel Statistics:\n")
        for user, channels in user_channel_stats.items():
            stats_file.write(f"{user}:\n")
            for channel, stats in channels.items():
                channel_name = channel.split('/')[-1]
                stats_file.write(f"  {channel_name}: Messages - {stats['messages']}, Attachments - {stats['attachments']}\n")

    print("Backup process complete.")

client.run(bt)
