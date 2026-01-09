/**
 * Database Migration Script
 * Run this to initialize the database schema
 */

const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');

// Database connection
const pool = new Pool({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
});

async function runMigration() {
  console.log('🚀 Starting database migration...');

  try {
    // Read schema file
    const schemaPath = path.join(__dirname, '../../database/schema.sql');
    const schema = fs.readFileSync(schemaPath, 'utf8');

    console.log('📖 Schema file loaded');

    // Execute schema
    await pool.query(schema);

    console.log('✅ Database schema created successfully!');
    console.log('📊 Tables created:');

    // List all tables
    const result = await pool.query(`
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = 'public'
      ORDER BY table_name;
    `);

    result.rows.forEach(row => {
      console.log('  - ' + row.table_name);
    });

    console.log('\n✨ Migration complete!');

  } catch (error) {
    console.error('❌ Migration failed:', error.message);
    console.error(error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

// Run migration
runMigration();
