
'use client';

import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
    FileText,
    Link as LinkIcon,
    Upload,
    RefreshCw,
    Trash2,
    Globe
} from "lucide-react";
import { toast } from "sonner";

export default function KnowledgePage() {
    const [systemPrompt, setSystemPrompt] = useState(
        "You are a helpful customer support assistant for Acme Corp. Answer questions based on the provided knowledge base."
    );

    // Mock Data
    const [documents, setDocuments] = useState([
        { id: 1, name: 'Pricing_2025.pdf', size: '1.2 MB', status: 'Indexed', date: '2025-05-10' },
        { id: 2, name: 'User_Manual_v2.pdf', size: '3.5 MB', status: 'Processing', date: '2025-05-11' },
    ]);

    const [urls, setUrls] = useState([
        { id: 1, url: 'https://acme.com/help', status: 'Indexed', date: '2025-05-01' },
        { id: 2, url: 'https://acme.com/pricing', status: 'Indexed', date: '2025-05-01' },
    ]);

    const handleSavePrompt = () => {
        toast.success("System prompt updated successfully");
    };

    const handleUpload = () => {
        toast.success("File uploaded (Mock). Processing started.");
        // Mock adding file
        setDocuments([...documents, {
            id: Date.now(),
            name: 'New_Upload.pdf',
            size: '0.5 MB',
            status: 'Pending',
            date: new Date().toISOString().split('T')[0]
        }]);
    };

    const handleAddUrl = (e: React.FormEvent) => {
        e.preventDefault();
        toast.success("URL added (Mock). Crawling started.");
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
                <Button>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Re-index All
                </Button>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                {/* System Prompt Section */}
                <Card className="md:col-span-2">
                    <CardHeader>
                        <CardTitle>AI Persona & System Prompt</CardTitle>
                        <CardDescription>
                            Define how your chatbot behaves and answers questions.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            <Label htmlFor="prompt">System Prompt</Label>
                            <Textarea
                                id="prompt"
                                className="min-h-[100px] font-mono text-sm"
                                value={systemPrompt}
                                onChange={(e) => setSystemPrompt(e.target.value)}
                            />
                        </div>
                    </CardContent>
                    <CardFooter>
                        <Button onClick={handleSavePrompt}>Save Changes</Button>
                    </CardFooter>
                </Card>

                {/* Knowledge Sources */}
                <div className="md:col-span-2">
                    <Tabs defaultValue="files" className="w-full">
                        <TabsList className="grid w-full grid-cols-2 lg:w-[400px]">
                            <TabsTrigger value="files">Files (PDF/Docs)</TabsTrigger>
                            <TabsTrigger value="urls">Website URLs</TabsTrigger>
                        </TabsList>

                        {/* Files Tab */}
                        <TabsContent value="files" className="space-y-4 mt-4">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Upload Documents</CardTitle>
                                    <CardDescription>
                                        Upload PDFs, Word docs, or Text files to train your bot.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="border-2 border-dashed rounded-lg p-8 text-center hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors cursor-pointer" onClick={handleUpload}>
                                        <div className="flex flex-col items-center gap-2">
                                            <Upload className="h-8 w-8 text-muted-foreground" />
                                            <p className="text-sm font-medium">Click to upload or drag and drop</p>
                                            <p className="text-xs text-muted-foreground">PDF, DOCX, TXT up to 10MB</p>
                                        </div>
                                    </div>

                                    <div className="mt-6 space-y-4">
                                        <h4 className="text-sm font-medium">Uploaded Files</h4>
                                        {documents.map((doc) => (
                                            <div key={doc.id} className="flex items-center justify-between p-3 border rounded-lg bg-card">
                                                <div className="flex items-center gap-3">
                                                    <div className="bg-primary/10 p-2 rounded">
                                                        <FileText className="h-4 w-4 text-primary" />
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-medium">{doc.name}</p>
                                                        <p className="text-xs text-muted-foreground">{doc.size} • {doc.date}</p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-3">
                                                    <Badge variant={doc.status === 'Indexed' ? 'secondary' : 'outline'}>
                                                        {doc.status}
                                                    </Badge>
                                                    <Button variant="ghost" size="icon" className="text-red-500 hover:text-red-600 hover:bg-red-50">
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        {/* URLs Tab */}
                        <TabsContent value="urls" className="space-y-4 mt-4">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Add URLs</CardTitle>
                                    <CardDescription>
                                        Crawl websites to extract knowledge.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <form onSubmit={handleAddUrl} className="flex gap-2">
                                        <div className="grid w-full items-center gap-1.5">
                                            <Label htmlFor="url" className="sr-only">URL</Label>
                                            <Input id="url" placeholder="https://example.com/pricing" />
                                        </div>
                                        <Button type="submit">Crawl</Button>
                                    </form>

                                    <div className="mt-6 space-y-4">
                                        <h4 className="text-sm font-medium">Crawled Pages</h4>
                                        {urls.map((item) => (
                                            <div key={item.id} className="flex items-center justify-between p-3 border rounded-lg bg-card">
                                                <div className="flex items-center gap-3">
                                                    <div className="bg-blue-500/10 p-2 rounded">
                                                        <Globe className="h-4 w-4 text-blue-500" />
                                                    </div>
                                                    <div className="overflow-hidden">
                                                        <p className="text-sm font-medium truncate max-w-[200px] sm:max-w-md">{item.url}</p>
                                                        <p className="text-xs text-muted-foreground">{item.date}</p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-3">
                                                    <Badge variant="secondary">{item.status}</Badge>
                                                    <Button variant="ghost" size="icon" className="text-red-500 hover:text-red-600 hover:bg-red-50">
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>
                    </Tabs>
                </div>
            </div>
        </div>
    );
}
