import './globals.css';
import { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Ralph UI - AI Agent Loop',
    description: 'Run Ralph autonomous coding agent with live logs and status',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    );
}
