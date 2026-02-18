import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Eye, EyeOff, Lock, Unlock, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { ModelManager } from './WhisperModelManager';
import { ParakeetModelManager } from './ParakeetModelManager';
import { configService, CustomASRConfig } from '@/services/configService';


export interface TranscriptModelProps {
    provider: 'localWhisper' | 'parakeet' | 'deepgram' | 'elevenLabs' | 'groq' | 'openai' | 'custom-asr';
    model: string;
    apiKey?: string | null;
}

export interface TranscriptSettingsProps {
    transcriptModelConfig: TranscriptModelProps;
    setTranscriptModelConfig: (config: TranscriptModelProps) => void;
    onModelSelect?: () => void;
}

export function TranscriptSettings({ transcriptModelConfig, setTranscriptModelConfig, onModelSelect }: TranscriptSettingsProps) {
    const [apiKey, setApiKey] = useState<string | null>(transcriptModelConfig.apiKey || null);
    const [showApiKey, setShowApiKey] = useState<boolean>(false);
    const [isApiKeyLocked, setIsApiKeyLocked] = useState<boolean>(true);
    const [isLockButtonVibrating, setIsLockButtonVibrating] = useState<boolean>(false);
    const [uiProvider, setUiProvider] = useState<TranscriptModelProps['provider']>(transcriptModelConfig.provider);

    // Custom ASR state
    const [asrEndpoint, setAsrEndpoint] = useState<string>('');
    const [asrApiKey, setAsrApiKey] = useState<string>('');
    const [asrModel, setAsrModel] = useState<string>('whisper-1');
    const [asrLanguage, setAsrLanguage] = useState<string>('');
    const [showAsrApiKey, setShowAsrApiKey] = useState<boolean>(false);
    const [asrTestStatus, setAsrTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
    const [asrTestMessage, setAsrTestMessage] = useState<string>('');
    const [asrSaving, setAsrSaving] = useState<boolean>(false);
    const [asrConfigLoaded, setAsrConfigLoaded] = useState<boolean>(false);

    // Sync uiProvider when backend config changes (e.g., after model selection or initial load)
    useEffect(() => {
        setUiProvider(transcriptModelConfig.provider);
    }, [transcriptModelConfig.provider]);

    useEffect(() => {
        if (transcriptModelConfig.provider === 'localWhisper' || transcriptModelConfig.provider === 'parakeet') {
            setApiKey(null);
        }
    }, [transcriptModelConfig.provider]);

    // Load custom ASR config when provider switches to custom-asr
    const loadAsrConfig = useCallback(async () => {
        if (asrConfigLoaded) return;
        try {
            const config = await configService.getCustomASRConfig();
            if (config) {
                setAsrEndpoint(config.endpoint || '');
                setAsrApiKey(config.apiKey || '');
                setAsrModel(config.model || 'whisper-1');
                setAsrLanguage(config.language || '');
            }
            setAsrConfigLoaded(true);
        } catch (err) {
            console.error('Error loading custom ASR config:', err);
        }
    }, [asrConfigLoaded]);

    useEffect(() => {
        if (uiProvider === 'custom-asr') {
            loadAsrConfig();
        }
    }, [uiProvider, loadAsrConfig]);

    const fetchApiKey = async (provider: string) => {
        try {
            const data = await invoke('api_get_transcript_api_key', { provider }) as string;
            setApiKey(data || '');
        } catch (err) {
            console.error('Error fetching API key:', err);
            setApiKey(null);
        }
    };
    const modelOptions: Record<string, string[]> = {
        localWhisper: [], // Model selection handled by ModelManager component
        parakeet: [], // Model selection handled by ParakeetModelManager component
        'custom-asr': [], // Model handled by custom ASR config form
        deepgram: ['nova-2-phonecall'],
        elevenLabs: ['eleven_multilingual_v2'],
        groq: ['llama-3.3-70b-versatile'],
        openai: ['gpt-4o'],
    };
    const requiresApiKey = transcriptModelConfig.provider === 'deepgram' || transcriptModelConfig.provider === 'elevenLabs' || transcriptModelConfig.provider === 'openai' || transcriptModelConfig.provider === 'groq';

    const handleInputClick = () => {
        if (isApiKeyLocked) {
            setIsLockButtonVibrating(true);
            setTimeout(() => setIsLockButtonVibrating(false), 500);
        }
    };

    const handleWhisperModelSelect = (modelName: string) => {
        setTranscriptModelConfig({
            ...transcriptModelConfig,
            provider: 'localWhisper',
            model: modelName
        });
        if (onModelSelect) {
            onModelSelect();
        }
    };

    const handleParakeetModelSelect = (modelName: string) => {
        setTranscriptModelConfig({
            ...transcriptModelConfig,
            provider: 'parakeet',
            model: modelName
        });
        if (onModelSelect) {
            onModelSelect();
        }
    };

    const handleAsrTestConnection = async () => {
        if (!asrEndpoint.trim() || !asrModel.trim()) {
            setAsrTestStatus('error');
            setAsrTestMessage('Endpoint URL and Model are required.');
            return;
        }

        setAsrTestStatus('testing');
        setAsrTestMessage('');

        try {
            const result = await configService.testCustomASRConnection(
                asrEndpoint.trim(),
                asrApiKey.trim() || null,
                asrModel.trim()
            );
            setAsrTestStatus('success');
            setAsrTestMessage(result.message || 'Connection successful');
        } catch (err) {
            setAsrTestStatus('error');
            setAsrTestMessage(typeof err === 'string' ? err : 'Connection test failed');
        }
    };

    const handleAsrSave = async () => {
        if (!asrEndpoint.trim() || !asrModel.trim()) {
            setAsrTestStatus('error');
            setAsrTestMessage('Endpoint URL and Model are required.');
            return;
        }

        setAsrSaving(true);
        try {
            const config: CustomASRConfig = {
                endpoint: asrEndpoint.trim(),
                apiKey: asrApiKey.trim() || null,
                model: asrModel.trim(),
                language: asrLanguage.trim() || null,
            };
            await configService.saveCustomASRConfig(config);
            setTranscriptModelConfig({
                ...transcriptModelConfig,
                provider: 'custom-asr',
                model: asrModel.trim(),
            });
            setAsrTestStatus('success');
            setAsrTestMessage('Configuration saved successfully');
            if (onModelSelect) {
                onModelSelect();
            }
        } catch (err) {
            setAsrTestStatus('error');
            setAsrTestMessage(typeof err === 'string' ? err : 'Failed to save configuration');
        } finally {
            setAsrSaving(false);
        }
    };

    return (
        <div>
            <div>
                <div className="space-y-4 pb-6">
                    <div>
                        <Label className="block text-sm font-medium text-gray-700 mb-1">
                            Transcript Model
                        </Label>
                        <div className="flex space-x-2 mx-1">
                            <Select
                                value={uiProvider}
                                onValueChange={(value) => {
                                    const provider = value as TranscriptModelProps['provider'];
                                    setUiProvider(provider);
                                    if (provider !== 'localWhisper' && provider !== 'parakeet' && provider !== 'custom-asr') {
                                        fetchApiKey(provider);
                                    }
                                }}
                            >
                                <SelectTrigger className='focus:ring-1 focus:ring-blue-500 focus:border-blue-500'>
                                    <SelectValue placeholder="Select provider" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="parakeet">Parakeet (Recommended - Real-time / Accurate)</SelectItem>
                                    <SelectItem value="localWhisper">Local Whisper (High Accuracy)</SelectItem>
                                    <SelectItem value="custom-asr">Custom Endpoint (OpenAI-compatible)</SelectItem>
                                    {/* <SelectItem value="deepgram">Deepgram (Backup)</SelectItem>
                                    <SelectItem value="elevenLabs">ElevenLabs</SelectItem>
                                    <SelectItem value="groq">Groq</SelectItem>
                                    <SelectItem value="openai">OpenAI</SelectItem> */}
                                </SelectContent>
                            </Select>

                            {uiProvider !== 'localWhisper' && uiProvider !== 'parakeet' && uiProvider !== 'custom-asr' && (
                                <Select
                                    value={transcriptModelConfig.model}
                                    onValueChange={(value) => {
                                        const model = value as TranscriptModelProps['model'];
                                        setTranscriptModelConfig({ ...transcriptModelConfig, provider: uiProvider, model });
                                    }}
                                >
                                    <SelectTrigger className='focus:ring-1 focus:ring-blue-500 focus:border-blue-500'>
                                        <SelectValue placeholder="Select model" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {(modelOptions[uiProvider] || []).map((model) => (
                                            <SelectItem key={model} value={model}>{model}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            )}

                        </div>
                    </div>

                    {uiProvider === 'localWhisper' && (
                        <div className="mt-6">
                            <ModelManager
                                selectedModel={transcriptModelConfig.provider === 'localWhisper' ? transcriptModelConfig.model : undefined}
                                onModelSelect={handleWhisperModelSelect}
                                autoSave={true}
                            />
                        </div>
                    )}

                    {uiProvider === 'parakeet' && (
                        <div className="mt-6">
                            <ParakeetModelManager
                                selectedModel={transcriptModelConfig.provider === 'parakeet' ? transcriptModelConfig.model : undefined}
                                onModelSelect={handleParakeetModelSelect}
                                autoSave={true}
                            />
                        </div>
                    )}

                    {uiProvider === 'custom-asr' && (
                        <div className="mt-4 space-y-3 mx-1">
                            <p className="text-xs text-gray-500">
                                Connect to any OpenAI-compatible speech recognition endpoint (e.g., Whisper API, Groq, local servers).
                            </p>

                            <div>
                                <Label className="block text-sm font-medium text-gray-700 mb-1">
                                    Endpoint URL <span className="text-red-500">*</span>
                                </Label>
                                <Input
                                    type="text"
                                    className="focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                                    value={asrEndpoint}
                                    onChange={(e) => { setAsrEndpoint(e.target.value); setAsrTestStatus('idle'); }}
                                    placeholder="https://api.openai.com/v1"
                                />
                                <p className="text-xs text-gray-400 mt-1">
                                    Base URL — /audio/transcriptions will be appended automatically
                                </p>
                            </div>

                            <div>
                                <Label className="block text-sm font-medium text-gray-700 mb-1">
                                    Model <span className="text-red-500">*</span>
                                </Label>
                                <Input
                                    type="text"
                                    className="focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                                    value={asrModel}
                                    onChange={(e) => { setAsrModel(e.target.value); setAsrTestStatus('idle'); }}
                                    placeholder="whisper-1"
                                />
                            </div>

                            <div>
                                <Label className="block text-sm font-medium text-gray-700 mb-1">
                                    API Key
                                </Label>
                                <div className="relative">
                                    <Input
                                        type={showAsrApiKey ? "text" : "password"}
                                        className="pr-10 focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                                        value={asrApiKey}
                                        onChange={(e) => { setAsrApiKey(e.target.value); setAsrTestStatus('idle'); }}
                                        placeholder="sk-... (optional)"
                                    />
                                    <div className="absolute inset-y-0 right-0 pr-1 flex items-center">
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => setShowAsrApiKey(!showAsrApiKey)}
                                        >
                                            {showAsrApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                        </Button>
                                    </div>
                                </div>
                            </div>

                            <div>
                                <Label className="block text-sm font-medium text-gray-700 mb-1">
                                    Language
                                </Label>
                                <Input
                                    type="text"
                                    className="focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                                    value={asrLanguage}
                                    onChange={(e) => setAsrLanguage(e.target.value)}
                                    placeholder="en (optional — auto-detect if empty)"
                                />
                            </div>

                            {/* Status message */}
                            {asrTestStatus !== 'idle' && asrTestStatus !== 'testing' && (
                                <div className={`flex items-center gap-2 text-sm ${asrTestStatus === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                                    {asrTestStatus === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                                    <span>{asrTestMessage}</span>
                                </div>
                            )}

                            {/* Action buttons */}
                            <div className="flex gap-2 pt-1">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleAsrTestConnection}
                                    disabled={asrTestStatus === 'testing' || !asrEndpoint.trim() || !asrModel.trim()}
                                >
                                    {asrTestStatus === 'testing' ? (
                                        <>
                                            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                            Testing...
                                        </>
                                    ) : (
                                        'Test Connection'
                                    )}
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleAsrSave}
                                    disabled={asrSaving || !asrEndpoint.trim() || !asrModel.trim()}
                                >
                                    {asrSaving ? (
                                        <>
                                            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                            Saving...
                                        </>
                                    ) : (
                                        'Save'
                                    )}
                                </Button>
                            </div>
                        </div>
                    )}

                    {requiresApiKey && (
                        <div>
                            <Label className="block text-sm font-medium text-gray-700 mb-1">
                                API Key
                            </Label>
                            <div className="relative mx-1">
                                <Input
                                    type={showApiKey ? "text" : "password"}
                                    className={`pr-24 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 ${isApiKeyLocked ? 'bg-gray-100 cursor-not-allowed' : ''
                                        }`}
                                    value={apiKey || ''}
                                    onChange={(e) => setApiKey(e.target.value)}
                                    disabled={isApiKeyLocked}
                                    onClick={handleInputClick}
                                    placeholder="Enter your API key"
                                />
                                {isApiKeyLocked && (
                                    <div
                                        onClick={handleInputClick}
                                        className="absolute inset-0 flex items-center justify-center bg-gray-100 bg-opacity-50 rounded-md cursor-not-allowed"
                                    />
                                )}
                                <div className="absolute inset-y-0 right-0 pr-1 flex items-center">
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => setIsApiKeyLocked(!isApiKeyLocked)}
                                        className={`transition-colors duration-200 ${isLockButtonVibrating ? 'animate-vibrate text-red-500' : ''
                                            }`}
                                        title={isApiKeyLocked ? "Unlock to edit" : "Lock to prevent editing"}
                                    >
                                        {isApiKeyLocked ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => setShowApiKey(!showApiKey)}
                                    >
                                        {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div >
    )
}
