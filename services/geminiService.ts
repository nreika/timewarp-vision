
import { GoogleGenAI, Type, GenerateContentResponse } from "@google/genai";
import { Target } from "../types";

const getAI = () => new GoogleGenAI({ apiKey: process.env.API_KEY || '' });

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
  
  const targetContext = target 
    ? `The user has specifically targeted an object at (x: ${target.x.toFixed(2)}, y: ${target.y.toFixed(2)}). 
       Focus on the movement, state change, or likely outcome for this specific object over the next 5 minutes.`
    : "Predict realistic changes for the most prominent elements in the scene over the next 5 minutes.";

  const prompt = `
    Analyze this camera frame. 
    ${targetContext}
    
    Predict 3 DISTINCT, realistic, and logically sound outcomes that could occur exactly 5 minutes from now.
    Avoid surreal or impossible events. Please ensure that the camera angle of view is strictly fixed. Do not change one's outfits and belongings. 
    
    Each outcome should be different (e.g., Scenario 1: Progressing a task, Scenario 2: Leaving the scene, Scenario 3: A slight environmental change).
    DO NOT change the perspective at all. Background should be identical.
    Return a JSON object with a "scenarios" array containing 3 items.
    Each item must have:
    1. "prediction_prompt": Detailed visual prompt for image generation.
    2. "scenario_description": Short Japanese text explaining the outcome.
    3. "label": A short unique label like "Timeline A", "Timeline B", "Timeline C".
  `;

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
        { text: `Modify this scene realistically for a 5-minute jump: ${predictionPrompt}. Keep composition consistent.` }
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
