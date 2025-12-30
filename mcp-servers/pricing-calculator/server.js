const express = require('express');
const app = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'pricing-calculator' });
});

// Pricing tiers for WhatsApp chatbot product
const PRICING_TIERS = {
  basic: {
    name: 'Básico',
    base_price: 299, // MXN per month
    included_messages: 1000,
    price_per_extra_message: 0.30,
    features: ['Respuestas automáticas 24/7', 'Hasta 1,000 mensajes/mes', 'Soporte por email']
  },
  professional: {
    name: 'Profesional',
    base_price: 799,
    included_messages: 5000,
    price_per_extra_message: 0.20,
    features: ['Todo lo del plan Básico', 'Hasta 5,000 mensajes/mes', 'Integraciones con CRM', 'Soporte prioritario']
  },
  enterprise: {
    name: 'Empresarial',
    base_price: 1999,
    included_messages: 20000,
    price_per_extra_message: 0.15,
    features: ['Todo lo del plan Profesional', 'Hasta 20,000 mensajes/mes', 'API personalizada', 'Gerente de cuenta dedicado', 'SLA garantizado']
  }
};

// MCP tool endpoint - calculate pricing
app.post('/tools/calculate_pricing', (req, res) => {
  try {
    const { message_volume, tier } = req.body;

    // Validate inputs
    if (!message_volume || typeof message_volume !== 'number') {
      return res.status(400).json({
        error: 'message_volume es requerido y debe ser un número'
      });
    }

    const selectedTier = tier || 'basic';
    const pricingTier = PRICING_TIERS[selectedTier];

    if (!pricingTier) {
      return res.status(400).json({
        error: `Plan no válido. Opciones: ${Object.keys(PRICING_TIERS).join(', ')}`
      });
    }

    // Calculate pricing
    const included = pricingTier.included_messages;
    const extra_messages = Math.max(0, message_volume - included);
    const extra_cost = extra_messages * pricingTier.price_per_extra_message;
    const total_cost = pricingTier.base_price + extra_cost;

    // Format response in Spanish
    const response = {
      plan: pricingTier.name,
      precio_base: `$${pricingTier.base_price.toFixed(2)} MXN/mes`,
      mensajes_incluidos: included.toLocaleString('es-MX'),
      mensajes_solicitados: message_volume.toLocaleString('es-MX'),
      mensajes_extra: extra_messages.toLocaleString('es-MX'),
      costo_extra: `$${extra_cost.toFixed(2)} MXN`,
      costo_total: `$${total_cost.toFixed(2)} MXN/mes`,
      caracteristicas: pricingTier.features,
      detalles: extra_messages > 0
        ? `Incluye ${included.toLocaleString('es-MX')} mensajes. ${extra_messages.toLocaleString('es-MX')} mensajes adicionales a $${pricingTier.price_per_extra_message} MXN cada uno.`
        : `Incluye hasta ${included.toLocaleString('es-MX')} mensajes por mes.`
    };

    res.json(response);
  } catch (error) {
    console.error('Error calculating pricing:', error);
    res.status(500).json({
      error: 'Error al calcular el precio',
      details: error.message
    });
  }
});

// MCP tool endpoint - list available plans
app.post('/tools/list_plans', (req, res) => {
  try {
    const plans = Object.keys(PRICING_TIERS).map(key => {
      const tier = PRICING_TIERS[key];
      return {
        id: key,
        nombre: tier.name,
        precio: `$${tier.base_price} MXN/mes`,
        mensajes_incluidos: tier.included_messages.toLocaleString('es-MX'),
        caracteristicas: tier.features
      };
    });

    res.json({
      planes_disponibles: plans,
      moneda: 'MXN',
      nota: 'Todos los precios en pesos mexicanos. Mensajes adicionales disponibles según plan.'
    });
  } catch (error) {
    console.error('Error listing plans:', error);
    res.status(500).json({
      error: 'Error al listar planes',
      details: error.message
    });
  }
});

// MCP tool discovery endpoint
app.get('/tools', (req, res) => {
  res.json({
    tools: [
      {
        name: 'calculate_pricing',
        description: 'Calcula el costo del chatbot de WhatsApp según el volumen de mensajes y plan seleccionado',
        input_schema: {
          type: 'object',
          properties: {
            message_volume: {
              type: 'number',
              description: 'Número estimado de mensajes por mes'
            },
            tier: {
              type: 'string',
              enum: ['basic', 'professional', 'enterprise'],
              description: 'Plan deseado (básico, profesional o empresarial)',
              default: 'basic'
            }
          },
          required: ['message_volume']
        }
      },
      {
        name: 'list_plans',
        description: 'Lista todos los planes disponibles con sus precios y características',
        input_schema: {
          type: 'object',
          properties: {}
        }
      }
    ]
  });
});

app.listen(PORT, () => {
  console.log(`Pricing Calculator MCP server running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`Tool discovery: http://localhost:${PORT}/tools`);
});
