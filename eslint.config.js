import js from '@eslint/js';

export default [
    js.configs.recommended,
    {
        files: ['frontend/**/*.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'script',
            globals: {
                window: 'readonly',
                document: 'readonly',
                console: 'readonly',
                fetch: 'readonly',
                AbortController: 'readonly',
                // Loaded from CDN in index.html
                marked: 'readonly',
            },
        },
        rules: {
            'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
            eqeqeq: ['error', 'always'],
            'prefer-const': 'error',
            'no-var': 'error',
        },
    },
];
