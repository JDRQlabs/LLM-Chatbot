const express = require('express');
const { Client } = require('pg');
const app = express();
const PORT = process.env.PORT || 3002;

app.use(express.json());

// Database connection config from environment
const DB_CONFIG = {
  host: process.env.DB_HOST || 'windmill_db',
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'changeme',
  database: process.env.DB_NAME || 'business_logic'
};

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'lead-capture' });
});

// MCP tool endpoint - capture lead
app.post('/tools/capture_lead', async (req, res) => {
  const client = new Client(DB_CONFIG);

  try {
    const {
      name,
      phone,
      email,
      company,
      estimated_messages,
      notes,
      chatbot_id
    } = req.body;

    // Validate required fields
    if (!phone) {
      return res.status(400).json({
        error: 'El número de teléfono es requerido'
      });
    }

    await client.connect();

    // Check if lead already exists
    const checkQuery = `
      SELECT id, created_at
      FROM leads
      WHERE phone = $1
      ORDER BY created_at DESC
      LIMIT 1
    `;
    const existingLead = await client.query(checkQuery, [phone]);

    if (existingLead.rows.length > 0) {
      // Update existing lead
      const updateQuery = `
        UPDATE leads
        SET
          name = COALESCE($1, name),
          email = COALESCE($2, email),
          company = COALESCE($3, company),
          estimated_messages = COALESCE($4, estimated_messages),
          notes = COALESCE($5, notes),
          chatbot_id = COALESCE($6, chatbot_id),
          updated_at = NOW(),
          contact_count = contact_count + 1
        WHERE id = $7
        RETURNING *
      `;

      const result = await client.query(updateQuery, [
        name,
        email,
        company,
        estimated_messages,
        notes,
        chatbot_id,
        existingLead.rows[0].id
      ]);

      await client.end();

      return res.json({
        success: true,
        action: 'actualizado',
        mensaje: `Lead actualizado exitosamente. Este contacto ha interactuado ${result.rows[0].contact_count} veces.`,
        lead: {
          id: result.rows[0].id,
          nombre: result.rows[0].name,
          telefono: result.rows[0].phone,
          email: result.rows[0].email,
          empresa: result.rows[0].company,
          mensajes_estimados: result.rows[0].estimated_messages,
          veces_contactado: result.rows[0].contact_count
        }
      });
    }

    // Insert new lead
    const insertQuery = `
      INSERT INTO leads (
        name,
        phone,
        email,
        company,
        estimated_messages,
        notes,
        chatbot_id,
        contact_count,
        created_at,
        updated_at
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, 1, NOW(), NOW())
      RETURNING *
    `;

    const result = await client.query(insertQuery, [
      name || null,
      phone,
      email || null,
      company || null,
      estimated_messages || null,
      notes || null,
      chatbot_id || null
    ]);

    await client.end();

    res.json({
      success: true,
      action: 'creado',
      mensaje: 'Lead guardado exitosamente. Un representante te contactará pronto.',
      lead: {
        id: result.rows[0].id,
        nombre: result.rows[0].name,
        telefono: result.rows[0].phone,
        email: result.rows[0].email,
        empresa: result.rows[0].company,
        mensajes_estimados: result.rows[0].estimated_messages
      }
    });

  } catch (error) {
    console.error('Error capturing lead:', error);

    if (client._connected) {
      await client.end();
    }

    res.status(500).json({
      error: 'Error al guardar la información del lead',
      details: error.message
    });
  }
});

// MCP tool endpoint - get lead info
app.post('/tools/get_lead', async (req, res) => {
  const client = new Client(DB_CONFIG);

  try {
    const { phone } = req.body;

    if (!phone) {
      return res.status(400).json({
        error: 'El número de teléfono es requerido'
      });
    }

    await client.connect();

    const query = `
      SELECT * FROM leads
      WHERE phone = $1
      ORDER BY created_at DESC
      LIMIT 1
    `;

    const result = await client.query(query, [phone]);
    await client.end();

    if (result.rows.length === 0) {
      return res.json({
        found: false,
        mensaje: 'No se encontró información de este contacto'
      });
    }

    const lead = result.rows[0];
    res.json({
      found: true,
      lead: {
        nombre: lead.name,
        telefono: lead.phone,
        email: lead.email,
        empresa: lead.company,
        mensajes_estimados: lead.estimated_messages,
        veces_contactado: lead.contact_count,
        primer_contacto: lead.created_at,
        ultimo_contacto: lead.updated_at
      }
    });

  } catch (error) {
    console.error('Error retrieving lead:', error);

    if (client._connected) {
      await client.end();
    }

    res.status(500).json({
      error: 'Error al buscar la información del lead',
      details: error.message
    });
  }
});

// MCP tool discovery endpoint
app.get('/tools', (req, res) => {
  res.json({
    tools: [
      {
        name: 'capture_lead',
        description: 'Guarda la información de un cliente potencial interesado en el chatbot de WhatsApp',
        input_schema: {
          type: 'object',
          properties: {
            phone: {
              type: 'string',
              description: 'Número de teléfono del cliente (requerido)'
            },
            name: {
              type: 'string',
              description: 'Nombre del cliente'
            },
            email: {
              type: 'string',
              description: 'Correo electrónico del cliente'
            },
            company: {
              type: 'string',
              description: 'Nombre de la empresa'
            },
            estimated_messages: {
              type: 'number',
              description: 'Volumen estimado de mensajes por mes'
            },
            notes: {
              type: 'string',
              description: 'Notas adicionales sobre el cliente'
            },
            chatbot_id: {
              type: 'string',
              description: 'ID del chatbot que capturó el lead'
            }
          },
          required: ['phone']
        }
      },
      {
        name: 'get_lead',
        description: 'Busca información de un cliente potencial por número de teléfono',
        input_schema: {
          type: 'object',
          properties: {
            phone: {
              type: 'string',
              description: 'Número de teléfono a buscar'
            }
          },
          required: ['phone']
        }
      }
    ]
  });
});

app.listen(PORT, () => {
  console.log(`Lead Capture MCP server running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`Tool discovery: http://localhost:${PORT}/tools`);
});
