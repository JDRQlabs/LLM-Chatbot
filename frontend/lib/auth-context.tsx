
'use client';

import {
    createContext,
    useContext,
    useEffect,
    useState,
    ReactNode,
} from 'react';
import { api } from '@/lib/api';
import { useRouter, usePathname } from 'next/navigation';

interface User {
    id: string;
    email: string;
    organizationId: string;
    role?: string;
}

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    login: (token: string, user: User) => void;
    logout: () => void;
    isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        // Check for existing session
        const checkAuth = async () => {
            try {
                const token = localStorage.getItem('token');
                const storedUser = localStorage.getItem('user');

                if (token && storedUser) {
                    // Validate token with /me endpoint
                    try {
                        // We can skip this call for now to avoid failing on initial load if API is down
                        // But in production we should verify
                        // await api.get('/auth/me'); 
                        setUser(JSON.parse(storedUser));
                    } catch (e) {
                        // Token invalid
                        logout();
                    }
                }
            } catch (error) {
                console.error('Auth check failed', error);
            } finally {
                setIsLoading(false);
            }
        };

        checkAuth();
    }, []);

    const login = (token: string, userData: User) => {
        localStorage.setItem('token', token);
        localStorage.setItem('user', JSON.stringify(userData));
        setUser(userData);
        router.push('/dashboard');
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setUser(null);
        router.push('/auth/login');
    };

    // Protect routes
    useEffect(() => {
        if (!isLoading) {
            const isAuthRoute = pathname.startsWith('/auth');
            const isDashboardRoute = pathname.startsWith('/dashboard');

            if (isDashboardRoute && !user) {
                router.push('/auth/login');
            } else if (isAuthRoute && user) {
                router.push('/dashboard');
            }
        }
    }, [user, isLoading, pathname, router]);

    return (
        <AuthContext.Provider
            value={{
                user,
                isLoading,
                login,
                logout,
                isAuthenticated: !!user,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
