
'use client';

import { useState } from 'react';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { MOCK_CONTACTS } from '@/lib/mock-data';
import { Button } from '@/components/ui/button';

interface ChatSidebarProps {
    onSelectContact: (contactId: string) => void;
    selectedContactId: string | null;
}

export function ChatSidebar({ onSelectContact, selectedContactId }: ChatSidebarProps) {
    const [search, setSearch] = useState('');
    // In real app, fetch contacts via React Query
    const contacts = MOCK_CONTACTS.filter(c =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.phoneNumber.includes(search)
    );

    return (
        <div className="flex bg-white dark:bg-gray-950 flex-col border-r h-full w-80">
            <div className="p-4 border-b space-y-4">
                <h2 className="font-semibold text-lg">Chats</h2>
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search contacts..."
                        className="pl-8"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
            </div>
            <ScrollArea className="flex-1">
                <div className="flex flex-col gap-1 p-2">
                    {contacts.map((contact) => (
                        <button
                            key={contact.id}
                            onClick={() => onSelectContact(contact.id)}
                            className={`flex items-start gap-3 p-3 text-left rounded-lg transition-colors hover:bg-accent ${selectedContactId === contact.id ? 'bg-accent' : ''
                                }`}
                        >
                            <Avatar>
                                <AvatarFallback>{contact.name.charAt(0)}</AvatarFallback>
                            </Avatar>
                            <div className="flex-1 overflow-hidden">
                                <div className="flex items-center justify-between">
                                    <span className="font-medium truncate">{contact.name}</span>
                                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                                        {new Date(contact.lastMessageAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                </div>
                                <p className="text-sm text-muted-foreground truncate">
                                    {contact.lastMessage}
                                </p>
                                {contact.tags.length > 0 && (
                                    <div className="flex gap-1 mt-1">
                                        {contact.tags.map(tag => (
                                            <Badge key={tag} variant="secondary" className="text-[10px] px-1 h-5">
                                                {tag}
                                            </Badge>
                                        ))}
                                    </div>
                                )}
                            </div>
                            {contact.unreadCount > 0 && (
                                <Badge className="bg-primary text-primary-foreground h-5 w-5 rounded-full p-0 flex items-center justify-center">
                                    {contact.unreadCount}
                                </Badge>
                            )}
                        </button>
                    ))}
                </div>
            </ScrollArea>
        </div>
    );
}
