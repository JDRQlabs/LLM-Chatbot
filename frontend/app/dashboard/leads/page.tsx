
'use client';

import { useState } from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { MoreHorizontal, ArrowUpDown, Search, Filter } from "lucide-react";
import { MOCK_LEADS } from "@/lib/mock-leads";

export default function LeadsPage() {
    const [searchTerm, setSearchTerm] = useState('');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

    // Filter and Sort Logic (Mock)
    const leads = MOCK_LEADS
        .filter(lead =>
            lead.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            lead.company.toLowerCase().includes(searchTerm.toLowerCase()) ||
            lead.email.toLowerCase().includes(searchTerm.toLowerCase())
        )
        .sort((a, b) => {
            const dateA = new Date(a.createdAt).getTime();
            const dateB = new Date(b.createdAt).getTime();
            return sortOrder === 'asc' ? dateA - dateB : dateB - dateA;
        });

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                <h1 className="text-2xl font-bold tracking-tight">Leads</h1>
                <div className="flex items-center gap-2 w-full sm:w-auto">
                    <div className="relative flex-1 sm:w-64">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search leads..."
                            className="pl-8"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>
                    <Button variant="outline" size="icon">
                        <Filter className="h-4 w-4" />
                    </Button>
                    <Button>Export CSV</Button>
                </div>
            </div>

            <div className="rounded-md border bg-white dark:bg-gray-950">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[200px]">Name</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="hidden md:table-cell">Company</TableHead>
                            <TableHead className="hidden md:table-cell">Score</TableHead>
                            <TableHead className="hidden lg:table-cell">
                                <Button
                                    variant="ghost"
                                    onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                                    className="-ml-4"
                                >
                                    Date Added
                                    <ArrowUpDown className="ml-2 h-4 w-4" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {leads.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} className="h-24 text-center">
                                    No results found.
                                </TableCell>
                            </TableRow>
                        ) : (
                            leads.map((lead) => (
                                <TableRow key={lead.id}>
                                    <TableCell className="font-medium">
                                        <div className="flex flex-col">
                                            <span>{lead.name}</span>
                                            <span className="text-xs text-muted-foreground">{lead.email}</span>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={lead.status === 'New' ? 'default' : 'secondary'}>
                                            {lead.status}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="hidden md:table-cell">{lead.company}</TableCell>
                                    <TableCell className="hidden md:table-cell">
                                        <div className="flex items-center gap-2">
                                            <div className="h-2 w-16 bg-secondary rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full ${lead.score > 80 ? 'bg-green-500' : 'bg-yellow-500'}`}
                                                    style={{ width: `${lead.score}%` }}
                                                />
                                            </div>
                                            <span className="text-xs text-muted-foreground">{lead.score}</span>
                                        </div>
                                    </TableCell>
                                    <TableCell className="hidden lg:table-cell">
                                        {new Date(lead.createdAt).toLocaleDateString()}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="ghost" className="h-8 w-8 p-0">
                                                    <span className="sr-only">Open menu</span>
                                                    <MoreHorizontal className="h-4 w-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end">
                                                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                                                <DropdownMenuItem>View Details</DropdownMenuItem>
                                                <DropdownMenuItem>View Chat History</DropdownMenuItem>
                                                <DropdownMenuItem className="text-red-600">Delete</DropdownMenuItem>
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
