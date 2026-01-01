
'use client';

import { useState } from 'react';
import { ChatSidebar } from '@/components/dashboard/chat/chat-sidebar';
import { ChatWindow } from '@/components/dashboard/chat/chat-window';
import { MessageSquare } from 'lucide-react';

export default function ChatPage() {
    const [selectedContactId, setSelectedContactId] = useState<string | null>(null);

    return (
        <div className="flex h-[calc(100vh-theme(spacing.16)-theme(spacing.8))] rounded-xl border bg-white dark:bg-gray-950 overflow-hidden shadow-sm">
            <ChatSidebar
                selectedContactId={selectedContactId}
                onSelectContact={setSelectedContactId}
            />

            <div className="flex-1 flex flex-col min-w-0">
                {selectedContactId ? (
                    <ChatWindow contactId={selectedContactId} />
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-50 dark:bg-slate-900/50">
                        <div className="bg-primary/10 p-4 rounded-full mb-4">
                            <MessageSquare className="h-8 w-8 text-primary" />
                        </div>
                        <h3 className="text-xl font-semibold mb-2">Select a conversation</h3>
                        <p className="text-muted-foreground max-w-sm">
                            Choose a contact from the list to view history and send messages.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
