// SQLite Database Module (Pure JavaScript Implementation)
const fs = require('fs');
const path = require('path');

class Database {
    constructor(dbPath = 'portable-os.db') {
        this.dbPath = path.resolve(dbPath);
        this.data = {};
        this.tables = {};
    }

    async open() {
        if (fs.existsSync(this.dbPath)) {
            const content = fs.readFileSync(this.dbPath, 'utf8');
            try {
                this.data = JSON.parse(content);
            } catch (e) {
                this.data = {};
            }
        }
        return this;
    }

    async close() {
        this.save();
        return this;
    }

    save() {
        fs.writeFileSync(this.dbPath, JSON.stringify(this.data, null, 2));
    }

    async createTable(tableName, columns) {
        this.tables[tableName] = columns;
        if (!this.data[tableName]) {
            this.data[tableName] = [];
        }
        this.save();
        return { success: true };
    }

    async insert(tableName, data) {
        if (!this.data[tableName]) {
            this.data[tableName] = [];
        }
        const id = this.data[tableName].length + 1;
        const record = { id, ...data, createdAt: new Date().toISOString() };
        this.data[tableName].push(record);
        this.save();
        return { lastID: id, changes: 1 };
    }

    async select(tableName, where = '', params = []) {
        if (!this.data[tableName]) return [];
        
        let results = this.data[tableName];
        
        if (where) {
            // Simple where clause parsing
            const [field, operator, value] = where.split(' ');
            results = results.filter(row => {
                switch (operator) {
                    case '=': return row[field] == value;
                    case '!=': return row[field] != value;
                    case '>': return row[field] > value;
                    case '<': return row[field] < value;
                    default: return true;
                }
            });
        }
        
        return results;
    }

    async get(tableName, where = '', params = []) {
        const results = await this.select(tableName, where, params);
        return results[0] || null;
    }

    async update(tableName, data, where, params = []) {
        if (!this.data[tableName]) return { changes: 0 };
        
        let updated = 0;
        this.data[tableName].forEach(row => {
            const [field, operator, value] = where.split(' ');
            let matches = false;
            switch (operator) {
                case '=': matches = row[field] == value; break;
                case '!=': matches = row[field] != value; break;
                case '>': matches = row[field] > value; break;
                case '<': matches = row[field] < value; break;
            }
            if (matches) {
                Object.assign(row, data, { updatedAt: new Date().toISOString() });
                updated++;
            }
        });
        
        this.save();
        return { changes: updated };
    }

    async delete(tableName, where, params = []) {
        if (!this.data[tableName]) return { changes: 0 };
        
        const before = this.data[tableName].length;
        const [field, operator, value] = where.split(' ');
        
        this.data[tableName] = this.data[tableName].filter(row => {
            switch (operator) {
                case '=': return row[field] != value;
                case '!=': return row[field] == value;
                case '>': return row[field] <= value;
                case '<': return row[field] >= value;
                default: return true;
            }
        });
        
        this.save();
        return { changes: before - this.data[tableName].length };
    }

    async count(tableName, where = '', params = []) {
        const results = await this.select(tableName, where, params);
        return results.length;
    }
}

module.exports = Database;
