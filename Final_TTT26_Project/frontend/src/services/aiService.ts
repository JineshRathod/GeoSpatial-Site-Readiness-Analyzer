import { GoogleGenerativeAI } from '@google/generative-ai';

// Initialize the API with the key from env or fallback
const apiKey = import.meta.env.VITE_GEMINI_API_KEY || '';
const genAI = new GoogleGenerativeAI(apiKey);

// We use the gemini-2.5-flash model for fast text generation
const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' });

export async function getLocationInsights(lat: number, lng: number, query: string, contextData: any) {
  try {
    const prompt = `
You are an expert geospatial analysis AI assistant. 
A user is analyzing a map and asking a question about a selected location at coordinates ${lat}, ${lng}.

### Analysis Data Available:
- Coordinates: ${lat}, ${lng}
- Overall Composite Score: ${contextData?.score?.totalScore ?? 'N/A'}/100
- Population Score: ${contextData?.score?.populationScore ?? 'N/A'}/100
- Accessibility Score: ${contextData?.score?.accessibilityScore ?? 'N/A'}/100
- Competition Score: ${contextData?.score?.competitionScore ?? 'N/A'}/100
- Flood Risk Level: ${contextData?.score?.flood?.riskLevel ?? 'N/A'} (Score: ${contextData?.score?.riskScore ?? 'N/A'}/100)
- Weather AQI: ${contextData?.score?.weather?.avgUsAqi ?? 'N/A'}
- Dominant Zoning: ${contextData?.score?.zoning?.dominantZone ?? 'N/A'}

### Nearby Landmarks:
${(contextData?.nearby?.slice(0, 5) || []).map((poi: any) => `- ${poi.title} (${poi.distanceKm?.toFixed(2)} km)`).join('\n') || 'None listed'}

### User Question:
"${query}"

Provide a concise, helpful, and insightful answer. Keep your response brief but highly relevant to the data provided above. Don't mention the raw scores directly unless strictly necessary, instead convert them into qualitative insights (e.g., "high foot traffic potential" rather than "population score 85"). Use Markdown for formatting if helpful.
`;

    const result = await model.generateContent(prompt);
    const response = await result.response;
    return response.text();
  } catch (error) {
    console.error('Error fetching AI insights:', error);
    throw error;
  }
}
