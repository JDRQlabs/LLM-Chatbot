
export const MOCK_CONTACTS = [
    {
        id: '1',
        name: 'Alice Johnson',
        phoneNumber: '+15550101',
        lastMessage: 'Thanks for the info!',
        lastMessageAt: '2025-05-10T14:30:00Z',
        unreadCount: 2,
        tags: ['lead', 'interested']
    },
    {
        id: '2',
        name: 'Bob Smith',
        phoneNumber: '+15550102',
        lastMessage: 'How much does the enterprise plan cost?',
        lastMessageAt: '2025-05-10T12:00:00Z',
        unreadCount: 0,
        tags: ['customer']
    },
    {
        id: '3',
        name: 'Charlie Brown',
        phoneNumber: '+15550103',
        lastMessage: 'I need help with my account.',
        lastMessageAt: '2025-05-09T09:15:00Z',
        unreadCount: 1,
        tags: ['support']
    }
];

export const MOCK_MESSAGES = [
    {
        id: '101',
        role: 'user',
        content: 'Hi, I saw your pricing page but I have a question.',
        createdAt: '2025-05-10T11:55:00Z'
    },
    {
        id: '102',
        role: 'assistant',
        content: 'Hello! I\'d be happy to help. What would you like to know?',
        createdAt: '2025-05-10T11:55:30Z'
    },
    {
        id: '103',
        role: 'user',
        content: 'How much does the enterprise plan cost?',
        createdAt: '2025-05-10T12:00:00Z'
    }
];
