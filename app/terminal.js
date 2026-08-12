// Portable OS Terminal
const readline = require('readline');

class Terminal {
  constructor() {
    this.commands = {
      help: this.help.bind(this),
      ls: this.ls.bind(this),
      cd: this.cd.bind(this),
      pwd: this.pwd.bind(this),
      cat: this.cat.bind(this),
      echo: this.echo.bind(this),
      clear: this.clear.bind(this),
      exit: this.exit.bind(this),
      status: this.status.bind(this)
    };
    this.cwd = process.cwd();
  }

  start() {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      prompt: 'portable-os> '
    });

    console.log('Portable OS Terminal v0.1.0');
    console.log('Type "help" for available commands.\n');

    rl.prompt();

    rl.on('line', (line) => {
      const [cmd, ...args] = line.trim().split(/\s+/);
      if (this.commands[cmd]) {
        this.commands[cmd](args);
      } else if (cmd) {
        console.log(`Unknown command: ${cmd}`);
      }
      rl.prompt();
    });

    rl.on('close', () => {
      console.log('\nGoodbye!');
      process.exit(0);
    });
  }

  help() {
    console.log('Available commands:');
    console.log('  help     - Show this help');
    console.log('  ls       - List files');
    console.log('  cd       - Change directory');
    console.log('  pwd      - Print working directory');
    console.log('  cat      - Show file contents');
    console.log('  echo     - Print text');
    console.log('  clear    - Clear screen');
    console.log('  status   - Show system status');
    console.log('  exit     - Exit terminal');
  }

  ls(args) {
    const dir = args[0] || this.cwd;
    try {
      const items = require('fs').readdirSync(dir);
      items.forEach(item => console.log(item));
    } catch (e) {
      console.log(`Cannot access ${dir}`);
    }
  }

  cd(args) {
    if (args[0]) {
      try {
        process.chdir(args[0]);
        this.cwd = process.cwd();
      } catch (e) {
        console.log(`Directory not found: ${args[0]}`);
      }
    } else {
      console.log(this.cwd);
    }
  }

  pwd() {
    console.log(this.cwd);
  }

  cat(args) {
    if (!args[0]) {
      console.log('Usage: cat <file>');
      return;
    }
    try {
      const content = require('fs').readFileSync(args[0], 'utf8');
      console.log(content);
    } catch (e) {
      console.log(`Cannot read ${args[0]}`);
    }
  }

  echo(args) {
    console.log(args.join(' '));
  }

  clear() {
    console.clear();
  }

  status() {
    const os = require('./core');
    console.log(JSON.stringify(new os().getStatus(), null, 2));
  }

  exit() {
    console.log('Goodbye!');
    process.exit(0);
  }
}

module.exports = new Terminal();

if (require.main === module) {
  module.exports.start();
}
