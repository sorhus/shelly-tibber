#!/usr/bin/env python3
"""
Energy Analysis Module
Analyzes energy usage during scheduled hours by comparing output data with Tibber consumption data
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone

from src.exceptions import TibberAPIError
from src.http_client import TibberClient
from src.models import HourlyEnergyUsage, DailyEnergySummary
from src.retry import RetryConfig

logger = logging.getLogger(__name__)

# Backward-compatible alias
EnergyUsage = HourlyEnergyUsage

class EnergyAnalyzer:
    """Analyzes energy usage during scheduled hours"""

    def __init__(self, config: Dict[str, Any], retry_config: RetryConfig = None):
        self.config = config
        self.home_id = config['tibber']['home_id']
        self.debug = config['tibber']['debug']

        # Create TibberClient for API calls
        self.tibber_client = TibberClient(
            token=config['tibber']['token'],
            timeout=30,
            retry_config=retry_config or RetryConfig(),
            debug=self.debug
        )
        
    def debug_log(self, message: str):
        """Debug logging function"""
        if self.debug:
            logger.debug(f"[DEBUG] {message}")
    
    def get_last_7_days_output(self) -> List[Dict[str, Any]]:
        """Get output data from the last 7 days"""
        logger.info("Loading output data from last 7 days...")
        
        output_data = []
        missing_dates = []
        today = datetime.now()
        
        for i in range(7):
            # The schedule for a given day is created the day before
            # So if we want to analyze July 24th, we need to look at output from July 23rd
            execution_date = today - timedelta(days=i+1)  # +1 because schedules are set day before
            target_date = today - timedelta(days=i)  # The actual day we want to analyze
            
            execution_date_str = execution_date.strftime('%Y-%m-%d')
            target_date_str = target_date.strftime('%Y-%m-%d')
            
            # Check for result file in the execution date directory
            result_file = os.path.join("output", execution_date_str, f"result_{execution_date_str}.json")
            
            if os.path.exists(result_file):
                try:
                    with open(result_file, 'r') as f:
                        data = json.load(f)
                        data['date'] = target_date_str  # Use target date for analysis
                        data['execution_date'] = execution_date_str  # Keep track of when it was created
                        output_data.append(data)
                        logger.info(f"✅ Loaded data for {target_date_str} (from {execution_date_str} execution)")
                except Exception as e:
                    logger.warning(f"❌ Failed to load data for {target_date_str} (from {execution_date_str}): {str(e)}")
                    missing_dates.append(target_date_str)
            else:
                logger.info(f"⚠️  No output data found for {target_date_str} (from {execution_date_str} execution)")
                missing_dates.append(target_date_str)
        
        logger.info(f"📊 Summary: {len(output_data)} days with data, {len(missing_dates)} days missing")
        if missing_dates:
            logger.info(f"📅 Missing dates: {', '.join(missing_dates)}")
        
        return output_data
    
    def fetch_tibber_consumption(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Fetch consumption data from Tibber API for a date range"""
        self.debug_log(f"Fetching consumption data from {start_date} to {end_date}")

        query = """
            query($homeId: ID!) {
              viewer {
                home(id: $homeId) {
                  consumption(resolution: HOURLY, last: 744) {
                    nodes {
                      from
                      to
                      unitCost
                      unitPrice
                      consumption
                      cost
                    }
                  }
                }
              }
            }
        """
        variables = {"homeId": self.home_id}

        # TibberClient.query() returns the 'data' portion directly
        data = self.tibber_client.query(query, variables)
        self.debug_log(f"API response keys: {list(data.keys()) if data else 'None'}")

        # Wrap in expected format for parse_consumption_data
        return {"data": data}
    
    def parse_consumption_data(self, response: Dict[str, Any], start_date: str, end_date: str) -> List[EnergyUsage]:
        """Parse Tibber consumption response into EnergyUsage objects"""
        self.debug_log("Parsing consumption data...")
        
        try:
            # Check if response is None or empty
            if not response:
                raise TibberAPIError("API response is empty or None")
            
            # Log the response structure for debugging
            self.debug_log(f"Response keys: {list(response.keys()) if response else 'None'}")
            
            # Check for errors in the response
            if "errors" in response:
                error_msg = f"GraphQL errors: {response['errors']}"
                logger.error(error_msg)
                raise TibberAPIError(error_msg, details={"errors": response["errors"]})
            
            # Check if data exists
            if "data" not in response:
                logger.error(f"Unexpected response structure: {response}")
                raise TibberAPIError(
                    "Unexpected Tibber API response structure",
                    details={"missing_field": "data"}
                )
            
            data = response["data"]
            if not data:
                raise TibberAPIError("Response data is empty")
            
            # Check if viewer exists
            if "viewer" not in data:
                logger.error(f"Response data missing 'viewer': {data}")
                raise TibberAPIError(
                    "Unexpected Tibber API response structure",
                    details={"missing_field": "viewer"}
                )
            
            viewer = data["viewer"]
            if not viewer:
                raise TibberAPIError("Viewer data is empty")
            
            # Check if home exists
            if "home" not in viewer:
                logger.error(f"Viewer data missing 'home': {viewer}")
                raise TibberAPIError(
                    "Unexpected Tibber API response structure",
                    details={"missing_field": "home"}
                )
            
            home = viewer["home"]
            if not home:
                raise TibberAPIError("Home data is empty")
            
            # Check if consumption exists
            if "consumption" not in home:
                logger.error(f"Home data missing 'consumption': {home}")
                raise TibberAPIError(
                    "Unexpected Tibber API response structure",
                    details={"missing_field": "consumption"}
                )
            
            consumption = home["consumption"]
            if not consumption:
                logger.warning("Consumption data is empty - no consumption data available")
                return []
            
            # Check if nodes exist
            if "nodes" not in consumption:
                logger.error(f"Consumption data missing 'nodes': {consumption}")
                raise TibberAPIError(
                    "Unexpected Tibber API response structure",
                    details={"missing_field": "nodes"}
                )
            
            consumption_nodes = consumption["nodes"]
            if not consumption_nodes:
                logger.warning("No consumption nodes found - no consumption data available")
                return []
            
            # Convert date strings to datetime for comparison (in local timezone)
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc).astimezone()
            end_dt = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)).replace(tzinfo=timezone.utc).astimezone()  # Include end date
            
            self.debug_log(f"Filtering for date range: {start_dt} to {end_dt}")
            
            energy_usage = []
            filtered_out = 0
            for node in consumption_nodes:
                # Parse the time range (Tibber data is already in local timezone)
                from_time_local = datetime.fromisoformat(node["from"])
                to_time_local = datetime.fromisoformat(node["to"])
                
                # Debug: show some sample dates
                if len(energy_usage) < 5:
                    self.debug_log(f"Sample data point: {from_time_local} local (date: {from_time_local.strftime('%Y-%m-%d')})")
                
                # Filter by date range (using local time)
                if from_time_local < start_dt or from_time_local >= end_dt:
                    filtered_out += 1
                    continue
                
                # Use the local time for the hour and date
                hour = from_time_local.hour
                date = from_time_local.strftime('%Y-%m-%d')
                
                energy_usage.append(EnergyUsage(
                    date=date,
                    hour=hour,
                    consumption=node.get("consumption", 0) or 0,
                    cost=node.get("cost", 0) or 0,
                    price=node.get("unitPrice", 0) or 0,
                    was_scheduled=False  # Will be set later
                ))
            
            self.debug_log(f"Total consumption nodes: {len(consumption_nodes)}")
            self.debug_log(f"Filtered out: {filtered_out}")
            
            if filtered_out == len(consumption_nodes) and len(consumption_nodes) > 0:
                # Show the date range of available data
                first_date = datetime.fromisoformat(consumption_nodes[0]["from"]).strftime('%Y-%m-%d')
                last_date = datetime.fromisoformat(consumption_nodes[-1]["from"]).strftime('%Y-%m-%d')
                logger.warning(f"No consumption data found for requested period {start_date} to {end_date}")
                logger.warning(f"Available data range: {first_date} to {last_date}")
                logger.warning("Consider using a date range that matches the available data for testing")
            
            self.debug_log(f"Parsed {len(energy_usage)} consumption data points for period {start_date} to {end_date}")
            return energy_usage
            
        except KeyError as e:
            logger.error(f"Missing key in response: {str(e)}")
            logger.error(f"Response structure: {response}")
            raise TibberAPIError(
                f"Unexpected Tibber API response structure",
                details={"missing_key": str(e)}
            )
        except TibberAPIError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to parse consumption response: {str(e)}")
            if response:
                logger.error(f"Response: {json.dumps(response, indent=2)}")
            raise TibberAPIError(
                f"Failed to parse consumption response: {str(e)}",
                details={"original_error": str(e)}
            )
    
    def mark_scheduled_hours(self, energy_usage: List[EnergyUsage], output_data: List[Dict[str, Any]]) -> List[EnergyUsage]:
        """Mark which hours were scheduled based on output data"""
        self.debug_log("Marking scheduled hours...")
        
        # Create a lookup for scheduled hours
        scheduled_hours = {}
        for output in output_data:
            date = output['date']
            if date not in scheduled_hours:
                scheduled_hours[date] = set()
            
            # Extract scheduled hours from consecutive_blocks
            for block in output.get('consecutive_blocks', []):
                start_time, end_time = block
                if isinstance(start_time, str):
                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                else:
                    start_dt = start_time
                    end_dt = end_time
                
                # Add all hours in the block
                current = start_dt
                while current < end_dt:
                    scheduled_hours[date].add(current.hour)
                    current += timedelta(hours=1)
        
        # Mark scheduled hours in energy usage data
        for usage in energy_usage:
            if usage.date in scheduled_hours and usage.hour in scheduled_hours[usage.date]:
                usage.was_scheduled = True
        
        scheduled_count = sum(1 for usage in energy_usage if usage.was_scheduled)
        self.debug_log(f"Marked {scheduled_count} hours as scheduled")
        
        return energy_usage
    
    def calculate_daily_summaries(self, energy_usage: List[EnergyUsage]) -> List[DailyEnergySummary]:
        """Calculate daily energy usage summaries"""
        self.debug_log("Calculating daily summaries...")
        
        # Group by date
        daily_data = {}
        for usage in energy_usage:
            if usage.date not in daily_data:
                daily_data[usage.date] = []
            daily_data[usage.date].append(usage)
        
        summaries = []
        for date, usages in daily_data.items():
            total_consumption = sum(u.consumption for u in usages)
            total_cost = sum(u.cost for u in usages)
            
            scheduled_usages = [u for u in usages if u.was_scheduled]
            scheduled_consumption = sum(u.consumption for u in scheduled_usages)
            scheduled_cost = sum(u.cost for u in scheduled_usages)
            scheduled_hours = len(scheduled_usages)
            
            summary = DailyEnergySummary(
                date=date,
                total_consumption=total_consumption,
                total_cost=total_cost,
                scheduled_consumption=scheduled_consumption,
                scheduled_cost=scheduled_cost,
                scheduled_hours=scheduled_hours,
                total_hours=len(usages),
            )
            summaries.append(summary)
        
        # Sort by date (newest first)
        summaries.sort(key=lambda x: x.date, reverse=True)
        
        self.debug_log(f"Calculated summaries for {len(summaries)} days")
        return summaries
    
    def analyze_last_7_days(self) -> Tuple[List[DailyEnergySummary], List[EnergyUsage]]:
        """Analyze energy usage for the last 7 days"""
        logger.info("Starting energy analysis for last 7 days...")
        
        try:
            # Get output data from last 7 days
            output_data = self.get_last_7_days_output()
            
            if not output_data:
                logger.warning("No output data found for analysis")
                return [], []
            
            # Log which dates we have data for
            available_dates = [output['date'] for output in output_data]
            logger.info(f"Found output data for {len(available_dates)} days: {', '.join(available_dates)}")
            
            # Calculate date range for Tibber API - always analyze the full 7 days
            today = datetime.now()
            end_date = today.strftime('%Y-%m-%d')
            start_date = (today - timedelta(days=6)).strftime('%Y-%m-%d')
            
            logger.info(f"Analysis period: {start_date} to {end_date} (7 days)")
            
            # Fetch consumption data from Tibber
            logger.info(f"Fetching consumption data from {start_date} to {end_date}")
            consumption_response = self.fetch_tibber_consumption(start_date, end_date)
            
            # Parse consumption data
            energy_usage = self.parse_consumption_data(consumption_response, start_date, end_date)
            
            # Mark which hours were scheduled
            energy_usage = self.mark_scheduled_hours(energy_usage, output_data)
            
            # Calculate daily summaries
            daily_summaries = self.calculate_daily_summaries(energy_usage)
            
            # Log which dates were actually analyzed
            analyzed_dates = [summary.date for summary in daily_summaries]
            
            # Calculate overall efficiency
            total_consumption = sum(summary.total_consumption for summary in daily_summaries)
            total_scheduled_consumption = sum(summary.scheduled_consumption for summary in daily_summaries)
            
            if total_consumption > 0:
                overall_efficiency = (total_scheduled_consumption / total_consumption) * 100
            else:
                overall_efficiency = 0.0
                logger.warning("No consumption data found - cannot calculate efficiency")
            
            logger.info(f"Energy analysis completed")
            logger.info(f"Analyzed {len(daily_summaries)} days with consumption data")
            logger.info(f"Dates analyzed: {', '.join(analyzed_dates)}")
            logger.info(f"Overall efficiency: {overall_efficiency:.1f}% of consumption during scheduled hours")
            logger.info(f"Total scheduled consumption: {total_scheduled_consumption:.2f} kWh")
            logger.info(f"Total consumption: {total_consumption:.2f} kWh")
            
            return daily_summaries, energy_usage
            
        except Exception as e:
            logger.error(f"Failed to analyze energy usage: {str(e)}")
            raise
    
    def save_analysis_results(self, daily_summaries: List[DailyEnergySummary], 
                            energy_usage: List[EnergyUsage]) -> str:
        """Save analysis results to a JSON file"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Create output directory
        output_dir = os.path.join("output", today)
        os.makedirs(output_dir, exist_ok=True)
        
        # Prepare data for JSON serialization
        summaries_data = []
        for summary in daily_summaries:
            summaries_data.append({
                'date': summary.date,
                'total_consumption': summary.total_consumption,
                'total_cost': summary.total_cost,
                'scheduled_consumption': summary.scheduled_consumption,
                'scheduled_cost': summary.scheduled_cost,
                'scheduled_hours': summary.scheduled_hours,
                'total_hours': summary.total_hours,
                'efficiency_ratio': summary.efficiency_ratio
            })
        
        usage_data = []
        for usage in energy_usage:
            usage_data.append({
                'date': usage.date,
                'hour': usage.hour,
                'consumption': usage.consumption,
                'cost': usage.cost,
                'price': usage.price,
                'was_scheduled': usage.was_scheduled
            })
        
        results = {
            'analysis_date': today,
            'period_days': len(daily_summaries),
            'daily_summaries': summaries_data,
            'hourly_usage': usage_data,
            'overall_stats': {
                'total_consumption': sum(s.total_consumption for s in daily_summaries),
                'total_scheduled_consumption': sum(s.scheduled_consumption for s in daily_summaries),
                'overall_efficiency': sum(s.scheduled_consumption for s in daily_summaries) / 
                                   sum(s.total_consumption for s in daily_summaries) if sum(s.total_consumption for s in daily_summaries) > 0 else 0
            }
        }
        
        # Save to file
        filename = os.path.join(output_dir, f"energy_analysis_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json")
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Energy analysis results saved to: {filename}")
        return filename

def main():
    """Main entry point for energy analysis"""
    import sys
    from src.config import get_config
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Load configuration
        config = get_config()
        
        # Set debug level if enabled
        if config['tibber']['debug']:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        
        # Create analyzer and run analysis
        analyzer = EnergyAnalyzer(config)
        daily_summaries, energy_usage = analyzer.analyze_last_7_days()
        
        # Save results
        if daily_summaries:
            filename = analyzer.save_analysis_results(daily_summaries, energy_usage)
            
            # Print summary
            print("\n📊 Energy Analysis Summary")
            print("=" * 50)
            print(f"📅 Analyzed {len(daily_summaries)} days")
            print()
            print("📈 Daily Consumption During Scheduled Hours:")
            print("-" * 50)
            
            for summary in daily_summaries:
                scheduled_kwh = summary.scheduled_consumption
                total_kwh = summary.total_consumption
                efficiency = summary.efficiency_ratio
                
                if scheduled_kwh > 0:
                    print(f"{summary.date}: {scheduled_kwh:.2f} kWh scheduled / {total_kwh:.2f} kWh total ({efficiency:.1%} efficiency)")
                else:
                    print(f"{summary.date}: {scheduled_kwh:.2f} kWh scheduled / {total_kwh:.2f} kWh total (no scheduled consumption)")
            
            total_scheduled = sum(s.scheduled_consumption for s in daily_summaries)
            total_overall = sum(s.total_consumption for s in daily_summaries)
            overall_efficiency = total_scheduled / total_overall if total_overall > 0 else 0
            
            print()
            print("📊 Summary Statistics:")
            print("-" * 50)
            print(f"🔋 Total scheduled consumption: {total_scheduled:.2f} kWh")
            print(f"⚡ Total overall consumption: {total_overall:.2f} kWh")
            print(f"📈 Overall efficiency: {overall_efficiency:.1%}")
            print(f"📅 Average daily scheduled: {total_scheduled/len(daily_summaries):.2f} kWh")
            print(f"📅 Average daily total: {total_overall/len(daily_summaries):.2f} kWh")
            
            # Show days with scheduled consumption
            days_with_scheduling = [s for s in daily_summaries if s.scheduled_consumption > 0]
            if days_with_scheduling:
                print()
                print("🔋 Days with Scheduled Consumption:")
                print("-" * 50)
                for summary in days_with_scheduling:
                    print(f"{summary.date}: {summary.scheduled_consumption:.2f} kWh during scheduled hours")
                
                avg_scheduled_when_active = sum(s.scheduled_consumption for s in days_with_scheduling) / len(days_with_scheduling)
                print(f"📊 Average when active: {avg_scheduled_when_active:.2f} kWh per day")
            else:
                print()
                print("⚠️  No days with scheduled consumption found")
            
            print(f"💾 Results saved to: {filename}")
        else:
            print("\n⚠️  No data available for analysis")
            print("   Make sure you have run the scheduling script for at least one day")
            print("   Check that output files exist in output/YYYY-MM-DD/result_*.json")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Energy analysis failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 