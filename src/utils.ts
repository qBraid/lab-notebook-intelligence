// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

export function removeAnsiChars(str: string): string {
    return str.replace(
        /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g,
        ''
    );
}

export async function waitForDuration(duration: number): Promise<void> {
    return new Promise(resolve => {
        setTimeout(() => {
            resolve();
        }, duration);
    });
}
