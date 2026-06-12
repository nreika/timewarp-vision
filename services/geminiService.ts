import { GoogleGenAI, Type } from "@google/genai";
import promptConfig from "../gemini-prompts.json";
import { Target } from "../types";

interface GeminiPromptConfig {
  editingGuide?: {
    editThisSection?: string;
    doNotEditSection?: string;
    keepPlaceholders?: string[];
    notes?: string[];
  };
  userEditable: {
    scenarioPrediction: {
      sceneAnalysisIntro: string;
      defaultTargetContext: string;
      targetedTargetContextTemplate: string;
      targetedTargetFocus: string;
      predictionRequest: string;
      variationGuidance: string;
      descriptionLanguageRule: string;
    };
    futureImageGeneration: {
      editInstructionTemplate: string;
    };
  };
  systemFixed: {
    scenarioPrediction: {
      hardRules: string[];
      outputFormatRules: string[];
    };
    futureImageGeneration: {
      hardRules: string[];
    };
  };
}

const getAI = () => new GoogleGenAI({ apiKey: process.env.API_KEY || '' });
const prompts = promptConfig as GeminiPromptConfig;

const joinLines = (lines: string[]): string => lines.join("\n").trim();
const joinPromptSections = (...sections: Array<string | string[]>): string =>
  sections
    .map((section) => (Array.isArray(section) ? joinLines(section) : section.trim()))
    .filter(Boolean)
    .join("\n\n")
    .trim();

const replacePlaceholders = (
  template: string,
  values: Record<string, string>
): string =>
  Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{{${key}}}`, value),
    template
  );

const buildDefaultScenarioContext = (): string =>
  prompts.userEditable.scenarioPrediction.defaultTargetContext.trim();

const buildTargetedScenarioContext = (target: Target): string =>
  joinPromptSections(
    replacePlaceholders(
      prompts.userEditable.scenarioPrediction.targetedTargetContextTemplate,
      {
        TARGET_X: target.x.toFixed(2),
        TARGET_Y: target.y.toFixed(2),
      }
    ),
    prompts.userEditable.scenarioPrediction.targetedTargetFocus
  );

const buildScenarioPredictionPrompt = (target: Target | null): string => {
  const targetContext = target
    ? buildTargetedScenarioContext(target)
    : buildDefaultScenarioContext();

  return joinPromptSections(
    prompts.userEditable.scenarioPrediction.sceneAnalysisIntro,
    targetContext,
    prompts.userEditable.scenarioPrediction.predictionRequest,
    prompts.systemFixed.scenarioPrediction.hardRules,
    prompts.userEditable.scenarioPrediction.variationGuidance,
    prompts.userEditable.scenarioPrediction.descriptionLanguageRule,
    prompts.systemFixed.scenarioPrediction.outputFormatRules
  );
};

const buildFutureImagePrompt = (predictionPrompt: string): string =>
  joinPromptSections(
    replacePlaceholders(
      prompts.userEditable.futureImageGeneration.editInstructionTemplate,
      { PREDICTION_PROMPT: predictionPrompt }
    ),
    prompts.systemFixed.futureImageGeneration.hardRules
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
