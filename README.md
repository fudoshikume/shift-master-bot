# Telegram Bot Project for Player Stats and Match Tracking

This repository contains a Telegram bot that tracks player stats, including solo losses, games played, wins, and losses from OpenDota's API. The bot allows interaction through commands to add and remove players, check player stats, and view solo losses.

## Features

- **Add Player**: Add players to the bot for tracking stats.
- **Remove Player**: Remove players from the list.
- **Stats**: Fetch detailed stats for a player.
- **Solo Losses**: Fetch players who had solo losses in the last hour.
- **Scheduled Tasks**: Automatic tasks that run at specified intervals to fetch player data and send notifications.

## Setup Instructions

### Requirements

To set up the bot, ensure that you have the following:

- Python 3.8+
- `pip` for installing Python dependencies
- A Telegram bot token from BotFather on Telegram

### Install Dependencies

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
3. Create a .env file in the root directory and add your Telegram bot token:
    ```bash
   TG_Token=your_telegram_bot_token_here

### Running the Bot
1. To start the bot, run the following command:
   ```bash
   python main.py
2. The bot will start and listen for commands in your Telegram chat.

### Commands
- **/start** - Start the bot.

- **/stats** - Get stats for a player.

- **/losses** - Get players with solo losses.

- **/addplayer** - Add a player to track.

- **/removeplayer** - Remove a player from the tracking list.

- **/gethelp** - Get a list of available commands.

### Contributing
Feel free to fork the project, make changes, and submit a pull request. Contributions are welcome!