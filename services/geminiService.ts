import { GoogleGenAI, Type } from "@google/genai";
import promptConfig from "../gemini-prompts.json";
import { Target } from "../types";

interface GeminiPromptConfig {
  scenarioPrediction: {
    defaultTargetContextLines: string[];
    targetedTargetContextLines: string[];
    instructionLines: string[];
  };
  futureImageGeneration: {
    instructionLines: string[];
  };
}

const getAI = () => new GoogleGenAI({ apiKey: process.env.API_KEY || '' });
const prompts = promptConfig as GeminiPromptConfig;

const joinLines = (lines: string[]): string => lines.join("\n").trim();

const replacePlaceholders = (
  template: string,
  values: Record<string, string>
): string =>
  Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{{${key}}}`, value),
    template
  );

const buildDefaultScenarioContext = (): string =>
  joinLines(prompts.scenarioPrediction.defaultTargetContextLines);

const buildTargetedScenarioContext = (target: Target): string =>
  replacePlaceholders(
    joinLines(prompts.scenarioPrediction.targetedTargetContextLines),
    {
      TARGET_X: target.x.toFixed(2),
      TARGET_Y: target.y.toFixed(2),
    }
  );

const buildScenarioPredictionPrompt = (target: Target | null): string => {
  const targetContext = target
    ? buildTargetedScenarioContext(target)
    : buildDefaultScenarioContext();

  return replacePlaceholders(
    joinLines(prompts.scenarioPrediction.instructionLines),
    { TARGET_CONTEXT: targetContext }
  );
};

const buildFutureImagePrompt = (predictionPrompt: string): string =>
  replacePlaceholders(
    joinLines(prompts.futureImageGeneration.instructionLines),
    { PREDICTION_PROMPT: predictionPrompt }
  );

export interface ScenarioResult {
  prediction_prompt: string;
  scenario_description: string;
  label: string;
}

/**
 * Step 1: Analyze frame and predict 3 distinct realistic 5-minute outcomes.
 */
export const predictFutureScenarios = async (base64Image: string, target: Target | null): Promise<ScenarioResult[]> => {
  const ai = getAI();
  const prompt = buildScenarioPredictionPrompt(target);

  const response = await ai.models.generateContent({
    model: 'gemini-3-flash-preview',
    contents: {
      parts: [
        { inlineData: { data: base64Image.split(',')[1], mimeType: 'image/jpeg' } },
        { text: prompt }
      ]
    },
    config: {
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          scenarios: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                prediction_prompt: { type: Type.STRING },
                scenario_description: { type: Type.STRING },
                label: { type: Type.STRING }
              },
              required: ["prediction_prompt", "scenario_description", "label"]
            }
          }
        },
        required: ["scenarios"]
      }
    }
  });

  const parsed = JSON.parse(response.text || "{}");
  return parsed.scenarios || [];
};

/**
 * Step 2: Generate a single future image based on a prompt.
 */
export const generateFutureImage = async (originalBase64: string, predictionPrompt: string): Promise<string> => {
  const ai = getAI();
  
  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash-image',
    contents: {
      parts: [
        { inlineData: { data: originalBase64.split(',')[1], mimeType: 'image/jpeg' } },
        { text: buildFutureImagePrompt(predictionPrompt) }
      ]
    },
    config: {
      imageConfig: {
        aspectRatio: "16:9"
      }
    }
  });

  for (const part of response.candidates?.[0]?.content?.parts || []) {
    if (part.inlineData) {
      return `data:image/png;base64,${part.inlineData.data}`;
    }
  }
  throw new Error("No image generated");
};
