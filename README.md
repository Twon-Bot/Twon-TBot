## Note: **PLEASE** fork the repository and submit a request if testing any changes - **do not** push to main please. *Thanks!*

# Twon-TBot  

A Discord bot designed for managing announcements, polls, schedules, and tracking in the PTCGP Server.  

### Core Bot Files  
- `bot.py` – Main bot file that runs the Discord bot.  
- `announce.py` – Manages all announcement-related functions.  
- `poll.py` – Test poll feature with plans for future implementations.  
- `help.py` – Provides command descriptions and usage help.  

### Announcement & Schedule Management  
- `delay.py` – Manages delayed announcements.  
- `schedule.py` – Handles the primary schedule output for the run.  
- `addingschedule.py` – Handles the start-of-run mini-schedule.  
- `delayed_announcements.json` – Stores delayed announcement data.  

### Utility & Tracking  
- `tracking.py` – Formats the pack tracking output.  
- `timestamp.py` – Convenient timestamp-code-generating function.  

### Miscellaneous  
- `delete.py` – Handles deletion commands.  
- `endcycle.py` – Outputs end-of-run/start-of-run output to several channels.  
- `expire.py` – Calculates pack expiration date/time.  
- `tony.py` – We care about Tony.  
- `write.py` – This is for me heheh.  

### Text Files  
- `announcements.txt` – Stores announcement messages.  
- `testannouncements.txt` – Stores test announcement messages.  

## Installation & Setup  

1. **Clone the Repository**  
   ```sh
   git clone https://github.com/Twon-Bot/Twon-TBot.git
   cd Twon-TBot
2. **Install Dependencies**
   ```sh
   pip install -r requirements.txt
3. **Setup Environment Variables**
- Create a **.env** file and add your bot token and other necessary credentials.
4. **Run the Bot**
   ```sh
   python bot.py
   
## Usage
- Use `!!help` for an overall outline of the bot's functions.
- ^^ If I missed any details that you're confused about, please reach out `@#01 Blimo` and I'll help asap!

## Contributing
If you'd like to contribute, please fork the repository and submit a pull request.

## License
This project is private and intended for use in the **2 Star Wonderpick Hunting** Server.
