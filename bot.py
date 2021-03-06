import os
import discord
from dotenv import load_dotenv
import datetime
import asyncio
from firebase import firebase
from requests.exceptions import ConnectionError

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB = os.getenv("BOSS_DB")


def printable_time_delta(delta):

    days = f"{delta.days} days, " if delta.days > 0 else ""
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    return f"{days}{hours} hours, {minutes} minutes"


def min_max_spawn(minimum_hours, random_hours):
    # Returns spawn window in minutes in format: (minimum_minutes, maximum_minutes)
    return (minimum_hours * 60, (minimum_hours + random_hours) * 60)


class CustomClient(discord.Client):
    def __init__(self):
        self.TIME_FORMAT = "%H:%M %a, %b %d %Y (UTC)"
        self.WINDOWS = "!windows"
        self.TOD = "!tod"
        self.ALERT = "!alert"
        self.AUTO_WINDOW = "!autowindow"

        self.WINDOW_CHECK_TIME = 20  # Time in seconds between window checks for alert

        self.BOSS_NAMES = {
            "aq": "Ant Queen",
            "core": "Core",
            "orfen": "Orfen",
            "zaken": "Zaken",
            "baium": "Baium",
            "antharas": "Antharas",
            "valakas": "Valakas",
            "frintezza": "Frintezza",
        }

        # Respawn times taken from:
        # https://l2reborn.com/support/faq/what-is-the-respawn-time-of-raid-bosses-epics-etc/
        self.SPAWN_TIMES = {
            "aq": min_max_spawn(24, 6),
            "core": min_max_spawn(30, 6),
            "orfen": min_max_spawn(30, 6),
            "zaken": min_max_spawn(40, 8),
            "baium": min_max_spawn(120, 8),
            "antharas": min_max_spawn(192, 8),
            "valakas": min_max_spawn(264, 0),
            "frintezza": min_max_spawn(48, 2),
        }

        self.fb = firebase.FirebaseApplication(DB, None)
        if self.fb.get("/raid-windows", "") is not None:
            result = self.fb.get("/raid-windows", "")
            self.fb_name = list(result.keys())[0]
            self.windows = result[self.fb_name]
        else:
            self.windows = {boss: ("None", "None") for boss in self.BOSS_NAMES.keys()}
            result = self.fb.post("/raid-windows", self.windows)
            self.fb_name = result["name"]

        if self.fb.get("/auto-window-channels", "") is not None:
            result = self.fb.get("/auto-window-channels", "")
            self.fb_auto_window_name = list(result.keys())[0]
            self.auto_window_channels = result[self.fb_auto_window_name]
        else:
            self.auto_window_channels = []
            result = self.fb.post("/auto-window-channels", self.auto_window_channels)
            self.fb_auto_window_name = result["name"]

        super().__init__()

    def convert_window(self, window):
        return datetime.datetime.strptime(window, self.TIME_FORMAT).replace(
            tzinfo=datetime.timezone.utc
        )

    def windows_response(self):
        try:
            self.windows = self.fb.get("/raid-windows", "")[self.fb_name]
        except ConnectionError:
            return None

        lines = []
        for boss, boss_verbose in self.BOSS_NAMES.items():
            window = self.windows[boss]
            countdown = self.create_window_string(window)
            lines.append([boss_verbose, f"{window[0]} - {window[1]}", f"({countdown})"])

        response = "```"
        col_widths = [len(word) for line in lines for word in line]
        for line in lines:
            response += "\n"
            response += "\t".join(word.ljust(col_widths[i]) for i, word in enumerate(line))
        response += "```"
        return response

    def check_if_window(self, window, now):
        if "None" in window:
            return False

        min_time = self.convert_window(window[0])

        diff = min_time - now
        if diff.days == 0 and diff.seconds < self.WINDOW_CHECK_TIME:
            return True
        else:
            return False

    def create_window_string(self, window):
        if "None" in window:
            return "window unknown"

        now = datetime.datetime.now(datetime.timezone.utc)

        min_time = self.convert_window(window[0])

        if min_time > now:
            # Case: window not opened yet
            return f"window opens in {printable_time_delta(min_time - now)}"

        max_time = self.convert_window(window[1])

        if max_time > now:
            # Case: window still open
            return f"window closes in {printable_time_delta(max_time - now)}"
        else:
            # Case: window already closed
            return f"window closed {printable_time_delta(abs(max_time - now))} ago"

    def add_auto_window(self, message):
        # Add channel to automatic window updater
        content_split = message.content.lower().split(" ")

        try:
            # Note: Only first channel mention in the message will be processed
            mentioned_channel = message.channel_mentions[0]
        except IndexError:
            return
        except TypeError:
            return

        if content_split[1] == "del":
            # Remove channel from list
            for i, channel in enumerate(self.auto_window_channels):
                if (channel["server_id"] == message.guild.id) and (
                    channel["channel_id"] == mentioned_channel.id
                ):
                    del self.auto_window_channels[i]
                    response = (
                        f"Removed automatic window updates from `#{mentioned_channel.name}` "
                        f" on server `{message.guild.name}`"
                    )
                    break  # Assume there's only one, duplicate checking is done at time of adding
            else:
                response = (
                    f"Channel `#{mentioned_channel.name}` on server `{message.guild.name}` "
                    "not found in list"
                )
        else:
            for channel in self.auto_window_channels:
                # Check for duplicate entry before adding
                if (channel["server_id"] == message.guild.id) and (
                    channel["channel_id"] == mentioned_channel.id
                ):
                    response = (
                        f"`#{mentioned_channel.name}` on server `{message.guild.name}` "
                        "already in list"
                    )
                    return response

            data = {
                "server_name": message.guild.name,
                "server_id": message.guild.id,
                "channel_name": mentioned_channel.name,
                "channel_id": mentioned_channel.id,
            }
            self.auto_window_channels.append(data)
            response = (
                f"Added automatic window updates to `#{mentioned_channel.name}` on server "
                f"`{message.guild.name}`"
            )

        self.fb.delete("/auto-window-channels/", self.fb_auto_window_name)
        result = self.fb.post("/auto-window-channels", self.auto_window_channels)
        self.fb_auto_window_name = result["name"]
        return response

    async def on_ready(self):
        await self.timed_events()

    async def on_message(self, message):
        if message.author == client.user:
            return  # This is needed to avoid bot responding to itself
        content = message.content.lower()  # Remove capitalisation from message for ease of parsing

        if content[: len(self.AUTO_WINDOW)] == self.AUTO_WINDOW:
            response = self.add_auto_window(message)
            await message.channel.send(response)
            return

        # if content[: len(self.WINDOWS)] == self.WINDOWS:
        #     response = self.windows_response()
        #     await message.channel.send(response)
        #     return

        if content[: len(self.TOD)] == self.TOD:
            content_split = content.split(" ")

            if len(content_split) < 4:
                await message.channel.send(
                    "Incorrect number of arguments for !tod, must follow format: "
                    "`!tod <aq|zaken|baium|antharas> year/month/day hours:minutes` "
                    "with hours in 24h format\n"
                    "For example: `!tod aq 2020/09/30 23:30`"
                )
                return

            boss_name = content_split[1].lower()
            time_of_death = " ".join(content_split[2:4])

            if boss_name in self.windows:
                t = datetime.datetime.strptime(time_of_death, "%Y/%m/%d %H:%M")
                spawn_times = self.SPAWN_TIMES[boss_name]
                self.windows[boss_name] = (
                    (t + datetime.timedelta(minutes=spawn_times[0])).strftime(self.TIME_FORMAT),
                    (t + datetime.timedelta(minutes=spawn_times[1])).strftime(self.TIME_FORMAT),
                )

                self.fb.put(f"/raid-windows/{self.fb_name}", boss_name, self.windows[boss_name])

                await message.channel.send(
                    f"Spawn time of {self.BOSS_NAMES[boss_name]} updated, new window:\n"
                    f"`{self.windows[boss_name][0]} - {self.windows[boss_name][1]}`"
                )
                return

    async def auto_window(self):
        time_format = "%H:%M:%S %a, %b %d %Y (UTC)"

        for chan in self.auto_window_channels:
            channel = client.get_channel(chan["channel_id"])

            try:
                last_message = await channel.fetch_message(channel.last_message_id)
                not_found = False
            except Exception as e:
                print(e)
                not_found = True

            update_time = datetime.datetime.now(datetime.timezone.utc).strftime(time_format)
            response = self.windows_response()

            if response is not None:
                content = response + f"\n```(last updated at {update_time})```"
            else:
                return

            if not_found or last_message.author != client.user:
                # If no previous message, or last message not by bot, make new post:
                await channel.send(content=content)
            else:
                # If last message was posted by bot, update that message:
                await last_message.edit(content=content)
        return

    async def boss_alert(self):
        now = datetime.datetime.now(
            datetime.timezone.utc
        )  # fix "now" here so it's same for all boss checks
        for boss, window in self.windows.items():
            if self.check_if_window(window, now) is True:
                # channel = client.get_channel(755624773400395928) # test server
                channel = client.get_channel(737070921944399962)  # #alliance-chat
                # TODO: Add way to add alert channels, and loop through them here
                msg = f"@everyone ```{self.BOSS_NAMES[boss]} window is open!```"
                await channel.send(msg)
        return

    async def timed_events(self):
        while True:
            await self.boss_alert()
            await self.auto_window()
            await asyncio.sleep(self.WINDOW_CHECK_TIME)


client = CustomClient()
client.run(TOKEN)
