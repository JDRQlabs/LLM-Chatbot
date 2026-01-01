
'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Phone, MoreVertical, Paperclip } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { MOCK_CONTACTS, MOCK_MESSAGES } from '@/lib/mock-data';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';

interface ChatWindowProps {
    contactId: string;
}

export function ChatWindow({ contactId }: ChatWindowProps) {
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState(MOCK_MESSAGES);
    const scrollRef = useRef<HTMLDivElement>(null);

    const contact = MOCK_CONTACTS.find(c => c.id === contactId);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, contactId]);

    const handleSend = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim()) return;

        // Phase 0: Check 24h window rule (Mock Logic)
        // In real app, backend would validation this.
        // For now, let's assume it's valid.

        const newMessage = {
            id: Date.now().toString(),
            role: 'assistant',
            content: input,
            createdAt: new Date().toISOString()
        };

        setMessages([...messages, newMessage]);
        setInput('');

        // Simulate optimistic update + "Send to backend"
        toast.success('Message sent (Mock)');
    };

    if (!contact) return <div className="flex-1 flex items-center justify-center">Contact not found</div>;

    return (
        <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-900/50">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b bg-white dark:bg-gray-950">
                <div className="flex items-center gap-3">
                    <Avatar>
                        <AvatarFallback>{contact.name.charAt(0)}</AvatarFallback>
                    </Avatar>
                    <div>
                        <h3 className="font-semibold">{contact.name}</h3>
                        <p className="text-xs text-muted-foreground">{contact.phoneNumber}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="icon">
                        <Phone className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon">
                        <MoreVertical className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Messages */}
            <ScrollArea className="flex-1 p-4" ref={scrollRef}>
                <div className="space-y-4">
                    {/* Date Separator Example */}
                    <div className="flex justify-center">
                        <span className="text-xs bg-gray-200 dark:bg-gray-800 px-2 py-1 rounded-full text-gray-500">
                            Today
                        </span>
                    </div>

                    {messages.map((msg) => (
                        <div
                            key={msg.id}
                            className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}
                        >
                            <div
                                className={`max-w-[70%] rounded-2xl px-4 py-2 ${msg.role === 'user'
                                        ? 'bg-white dark:bg-gray-800 border'
                                        : 'bg-primary text-primary-foreground'
                                    }`}
                            >
                                <p className="text-sm">{msg.content}</p>
                                <span className={`text-[10px] block mt-1 text-right ${msg.role === 'user' ? 'text-gray-400' : 'text-primary-foreground/70'
                                    }`}>
                                    {new Date(msg.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>

            {/* Input Area */}
            <div className="p-4 bg-white dark:bg-gray-950 border-t">
                <form onSubmit={handleSend} className="flex gap-2 items-end">
                    <Button type="button" variant="ghost" size="icon" className="shrink-0">
                        <Paperclip className="h-5 w-5 text-gray-400" />
                    </Button>
                    <Input
                        placeholder="Type a message..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        className="flex-1 bg-gray-50 dark:bg-gray-900 border-0 focus-visible:ring-1"
                    />
                    <Button type="submit" size="icon" disabled={!input.trim()}>
                        <Send className="h-4 w-4" />
                    </Button>
                </form>
                <div className="mt-2 text-center text-xs text-gray-400">
                    24h window active • You can reply
                </div>
            </div>
        </div>
    );
}
