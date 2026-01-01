
import { MOCK_CONTACTS } from "./mock-data";

export const MOCK_LEADS = [
    ...MOCK_CONTACTS.map(c => ({
        ...c,
        status: c.tags.includes('lead') ? 'New' : 'Customer',
        email: `${c.name.toLowerCase().replace(' ', '.')}@example.com`,
        company: 'Acme Inc',
        source: 'WhatsApp',
        createdAt: '2025-05-01T10:00:00Z',
        score: 85
    })),
    {
        id: '4',
        name: 'David Miller',
        phoneNumber: '+15550104',
        status: 'Qualified',
        email: 'david@techcorp.com',
        company: 'TechCorp',
        source: 'Website',
        createdAt: '2025-05-11T08:30:00Z',
        score: 92,
        unreadCount: 0,
        tags: ['lead', 'qualified'],
        lastMessage: 'Ready to sign.',
        lastMessageAt: '2025-05-11T08:30:00Z'
    }
];
