#### This file was partially taken from other repo
#### We don't use it yet as other APIs are providing the sentiment analysis
#### It is here for future use and development

import json
import os
import logging.config
from typing import List, Tuple, Optional
import datetime
from dotenv import load_dotenv
import praw
from rich.console import Console
from rich.traceback import install
from rich.progress import track
import threading
from threading import Event
import time
from logger import get_logger

console = Console(record=True)
install()

logging.config.dictConfig({"version": 1, "disable_existing_loggers": True})

logger = get_logger(__name__)

r_FinInvMarket = [
    "wallstreetbets",
    # "Daytrading",
    # "algotrading",
    # "realestateinvesting",
    # "financialindependence",
    # "investing",
    # "stocks",
    # "StockMarket",
    # "economy",
    # "GlobalMarkets",
    # "options",
    # "finance",
    # "dividends",
    # "pennystocks",
    # "FinancialPlanning",
    # "personalfinance",
    # "retirement",
    # "CreditCards",
    # "tax",
    # "FinanceNews",
    # "povertyfinance",
    # "SecurityAnalysis",
    # "PFtools",
]

class collect:
    def __init__(
        self,
        reddit_client: praw.Reddit,
    ):
        """
        Initialize the Collect instance for collecting data from Reddit and storing it in ChromaDB.

        Args:
            reddit_client (praw.Reddit): The Reddit client used for interacting with Reddit's API.

        Note:
            The method also checks for the existence of the 'error_log' folder and creates it if not present.
        """
        self.reddit = reddit_client

        self.error_log_path = os.path.join(os.getcwd(), "error_log")
        os.makedirs(self.error_log_path, exist_ok=True)

    def redditor_data(self, praw_models: praw.models, insert: bool) -> Tuple[str, bool]:
        """
        Collects and stores data related to a specific Redditor.

        Args:
            praw_models (praw.models): An object containing praw models.
            insert (bool): Insert redditor data to DB.

        Returns:
            Tuple[str, bool]: A tuple containing the unique identifier of the Redditor collected and a boolean indicating whether the Redditor was inserted in the database.
        """
        redditor = praw_models.author

        if insert is True:
            if hasattr(redditor, "id"):
                redditor_id = redditor.id
                # Prepare redditor document (skip existence check)
                name = redditor.name
                created_at = datetime.datetime.fromtimestamp(
                    redditor.created_utc
                ).isoformat()
                # Flatten karma dict into separate fields
                karma_comment = redditor.comment_karma
                karma_link = redditor.link_karma
                karma_awardee = redditor.awardee_karma
                karma_awarder = redditor.awarder_karma
                karma_total = redditor.total_karma
                is_gold = redditor.is_gold
                removed = "active"
            else:
                if hasattr(redditor, "name") and getattr(redditor, "is_suspended", False):
                    redditor_id = "suspended:" + redditor.name
                    name = redditor.name
                    created_at = None
                    # In suspended case, only some karma info may be available
                    karma_comment = None
                    karma_link = None
                    karma_awardee = redditor.awardee_karma
                    karma_awarder = redditor.awarder_karma
                    karma_total = redditor.total_karma
                    is_gold = None
                    removed = "suspended"
                elif redditor is None:
                    redditor_id = "deleted"
                    return redditor_id, False
            row = {
                "redditor_id": redditor_id,
                "name": name,
                "created_at": created_at,
                "karma_comment": karma_comment,
                "karma_link": karma_link,
                "karma_awardee": karma_awardee,
                "karma_awarder": karma_awarder,
                "karma_total": karma_total,
                "is_gold": is_gold,
                "removed": removed,
            }
            self.redditor_saver.add_document(row, redditor_id)
            logger.debug(f"Inserted redditor {redditor_id}")
            return redditor_id, True
        else:
            # Return id without insertion
            redditor_id = getattr(redditor, "id", "unknown")
            return redditor_id, False

    def submission_data(
        self,
        submission: praw.models.reddit.submission.Submission,
        insert_redditor: bool = True,
    ) -> Tuple[str, int, int]:
        """
        Collects and stores submissions and associated users in a specified subreddit.

        Args:
            submission (praw.models.reddit.submission.Submission): The praw Submission object representing the submission.

        Returns:
            Tuple[str, int, int]: A tuple containing the submission id, the count of inserted submissions and the count of inserted Redditors.
        """
        accessed_at = datetime.datetime.now(datetime.UTC)
        submission_id = submission.id
        submission_inserted = False
        redditor_inserted = False

        console.log(
            "Submission [bold red]{}[/] not in DB. Adding to DB-{}".format(
                submission_id, self.submission_saver.collection_name
            )
        )

        redditor_id, redditor_inserted = self.redditor_data(
            submission, insert=insert_redditor
        )  # consider not saving if redditor_id is "deleted"
        created_at = datetime.datetime.fromtimestamp(submission.created_utc)
        title = submission.title

        selftext = submission.selftext

        subreddit = submission.subreddit.display_name
        permalink = "https://www.reddit.com" + submission.permalink
        attachment = None

        if submission.is_reddit_media_domain:
            if submission.is_video:
                attachment = {"video": submission.url}
            else:
                if ".jpg" in submission.url:
                    attachment = {"jpg": submission.url}
                elif ".png" in submission.url:
                    attachment = {"png": submission.url}
                elif ".gif" in submission.url:
                    attachment = {"gif": submission.url}
        else:
            if submission.is_self:
                attachment = None
            else:
                attachment = {"url": submission.url}

        if hasattr(submission, "poll_data"):
            vote_ends_at = datetime.datetime.fromtimestamp(
                submission.poll_data.voting_end_timestamp / 1000
            )
            options = submission.poll_data.options
            Options = {}
            for option in options:
                Options.update({f"{option}": "unavaliable"})
            poll = {
                "total_vote_count": 0,
                "vote_ends_at": vote_ends_at.isoformat(timespec="seconds"),
                "options": Options,
                "closed": bool,
            }

            if vote_ends_at > datetime.datetime.now(datetime.UTC):
                poll["total_vote_count"] = submission.poll_data.total_vote_count
                poll["closed"] = False
            else:
                poll["total_vote_count"] = submission.poll_data.total_vote_count
                poll["closed"] = True
                for option in options:
                    Options[f"{option}"] = f"{option.vote_count}"
        else:
            poll = None

        flair = {
            "link": submission.link_flair_text,
            "author": submission.author_flair_text,
        }

        if submission.total_awards_received == 0:
            awards = {
                "total_awards_count": 0,
                "total_awards_price": 0,
                "list": None,
            }
        else:
            awards = {"total_awards_count": submission.total_awards_received}
            awards_list = {}
            total_awards_price = 0

            for awardings in submission.all_awardings:
                awards_list.update(
                    {
                        awardings["name"]: [
                            awardings["count"],
                            awardings["coin_price"],
                        ]
                    }
                )
                total_awards_price += awardings["coin_price"] * awardings["count"]
            awards.update({"total_awards_price": total_awards_price})
            awards["list"] = awards_list

        score = {accessed_at.isoformat(timespec="seconds"): submission.score}
        upvote_ratio = {
            accessed_at.isoformat(timespec="seconds"): submission.upvote_ratio
        }
        num_comments = {
            accessed_at.isoformat(timespec="seconds"): submission.num_comments
        }

        if submission.edited is False:
            edited = False
        else:
            edited = True  # if edited, submission.edited returns when the post was edited in terms of unix

        archived = submission.archived
        # archived_at = created_at + relativedelta(months=+6)

        if submission.removed_by_category is None:
            removed = False
        else:
            removed = True  # if removed, submission.removed_by_category returns the reason why the post was removed

        row = {
            "submission_id": submission_id,
            "redditor_id": redditor_id,
            "created_at": created_at.isoformat(),
            "title": title,
            "text": selftext,
            "subreddit": subreddit,
            "permalink": permalink,
            "attachment": attachment,
            "poll": poll,
            "flair": flair,
            "awards": awards,
            "score": score,
            "upvote_ratio": upvote_ratio,
            "num_comments": num_comments,
            "edited": edited,
            "archived": archived,
            "removed": removed,
        }

        self.submission_saver.add_document(row, submission_id)
        logger.debug(f"Inserted submission {submission_id}")
        submission_inserted = True

        return submission_id, submission_inserted, redditor_inserted

    def comment_data(
        self,
        comments: List[praw.models.reddit.comment.Comment],
        insert_redditor: bool = True,
    ) -> Tuple[int, int]:
        """
        Collects and stores comment data associated with a list of comments.

        Args:
            comments (List[praw.models.reddit.comment.Comment]): A list of praw Comment objects to collect and store.

        Returns:
            Tuple[int, int]: A tuple containing the count of inserted comments and the count of inserted Redditors.
        """
        comment_inserted_count = 0
        redditor_inserted_count = 0

        for comment in comments:
            accessed_at = datetime.datetime.utcnow()
            try:
                comment_id = comment.id
                console.log(
                    "Adding comment [bold red]{}[/] to DB-{}".format(
                        comment_id,
                        self.comment_saver.collection_name,
                    )
                )
                link_id = comment.link_id.replace("t3_", "")
                subreddit = str(comment.subreddit)
                parent_id = comment.parent_id
                redditor_id, redditor_inserted = self.redditor_data(
                    comment, insert=insert_redditor
                )  # consider not saving if redditor_id is "deleted"
                if redditor_inserted is True:
                    redditor_inserted_count += 1

                created_at = datetime.datetime.fromtimestamp(comment.created_utc)

                selfbody = comment.body
                removed = None

                if comment.edited is False:
                    edited = False
                else:
                    edited = True

                if selfbody == "[deleted]":
                    selfbody = None
                    removed = "deleted"
                elif selfbody == "[removed]":
                    selfbody = None
                    removed = "removed"

                score = {accessed_at.isoformat(timespec="seconds"): comment.score}

                row = {
                    "comment_id": comment_id,
                    "link_id": link_id,
                    "subreddit": subreddit,
                    "parent_id": parent_id,
                    "redditor_id": redditor_id,
                    "created_at": created_at.isoformat(),
                    "body": selfbody,
                    "score": score,
                    "edited": edited,
                    "removed": removed,
                }

                self.comment_saver.add_document(row, comment_id)
                logger.debug(f"Inserted comment {comment_id}")
                comment_inserted_count += 1

            except Exception as error:
                logger.error(f"Error processing comment {comment.id}: {error}")
                console.print_exception()
                console.save_html(
                    os.path.join(self.error_log_path, f"t1_{comment.id}.html")
                )
                continue

        return comment_inserted_count, redditor_inserted_count

    def subreddit_submission(
        self,
        subreddits: List[str],
        sort_types: List[str],
        limit: int = 10,
    ) -> None:
        """
        Lazy collection. Collects and stores submissions and associated users in specified subreddits.

        Args:
            subreddits (List[str]): A list of subreddit names to collect submissions from.
            sort_types (List[str]): A list of sorting types for submissions (e.g., 'hot', 'new', 'rising', 'top', 'controversial').
            limit (int, optional): The maximum number of submissions to collect for each subreddit. Defaults to 10. Set to None to fetch maximum number of submissions.

        Returns:
            None. Prints the count of collected submissions and user data to the console.
        """

        with console.status(
            "[bold green]Collecting submissions and users from subreddit(s)...",
            spinner="aesthetic",
        ):
            total_submission_inserted_count = 0
            total_redditor_inserted_count = 0
            for subreddit in subreddits:
                logger.info(f"Processing subreddit: {subreddit}")
                for sort_type in sort_types:
                    logger.info(f"Sort type: {sort_type}")
                    r_ = self.reddit.subreddit(subreddit)
                    for submission in getattr(r_, sort_type)(limit=limit):
                        try:
                            (
                                submission_id,
                                submission_inserted,
                                redditor_inserted,
                            ) = self.submission_data(
                                submission=submission
                            )

                            if submission_inserted is True:
                                total_submission_inserted_count += 1
                            if redditor_inserted is True:
                                total_redditor_inserted_count += 1

                        except Exception as error:
                            logger.error(f"Error processing submission {submission_id}: {error}")
                            console.print_exception()
                            console.save_html(
                                os.path.join(
                                    self.error_log_path, f"t3_{submission_id}.html"
                                )
                            )
                            continue

        return logger.info(
            f"{total_submission_inserted_count} submissions and {total_redditor_inserted_count} users collected from subreddit(s) {subreddits}"
        )

    def subreddit_comment(
        self,
        subreddits: List[str],
        sort_types: List[str],
        limit: int = 10,
        level: Optional[int] = 1,
    ) -> None:
        """
        Lazy collection. Collects and stores comments and associated users in specified subreddits.

        Args:
            subreddits (List[str]): A list of subreddit names to collect comments from.
            sort_types (List[str]): A list of sorting types for submissions (e.g., 'hot', 'new', 'rising', 'top', 'controversial').
            limit (int, optional): The maximum number of submissions to collect comments from (for each subreddit). Defaults to 10. Set to None to fetch maximum number of submissions.
            level (int, optional): The depth to which comment replies should be fetched. Defaults to 1. Set to None to fetch all comment replies.

        Returns:
            None. Prints the count of collected comments and user data to the console.
        """

        with console.status(
            "[bold green]Collecting comments and users from subreddit(s)...",
            spinner="aesthetic",
        ):
            total_comment_inserted_count = 0
            total_redditor_inserted_count = 0

            for subreddit in subreddits:
                logger.info(f"Processing subreddit: {subreddit}")
                for sort_type in sort_types:
                    logger.info(f"Sort type: {sort_type}")

                    r_ = self.reddit.subreddit(subreddit)

                    for submission in getattr(r_, sort_type)(limit=limit):
                        try:
                            submission_id = submission.id

                            link_id_filter = (
                                self.comment_db.select("link_id")
                                .eq("link_id", submission_id)
                                .execute()
                                .dict()["data"]
                            )

                            if len(link_id_filter) >= 1:
                                console.log(
                                    "Submission Link [bold red]{}[/] already in DB-{}".format(
                                        submission_id, self.comment_saver.collection_name
                                    )
                                )

                            else:
                                submission.comments.replace_more(limit=level)
                                # len(submission.comments.list()) would often give different values to submission.num_comments
                                comments = submission.comments.list()
                                (
                                    comment_inserted_count,
                                    redditor_inserted_count,
                                ) = self.comment_data(
                                    comments=comments
                                )
                                total_comment_inserted_count += comment_inserted_count
                                total_redditor_inserted_count += redditor_inserted_count

                        except Exception as error:
                            logger.error(f"Error processing submission {submission.id}: {error}")
                            console.print_exception()
                            console.save_html(
                                os.path.join(
                                    self.error_log_path, f"t3_{submission.id}.html"
                                )
                            )
                            continue

        return logger.info(
            f"{total_comment_inserted_count} comments and {total_redditor_inserted_count} users collected from subreddit(s) {subreddits}"
        )

    def subreddit_submission_and_comment(
        self,
        subreddits: List[str],
        sort_types: List[str],
        limit: int = 10,
        level: int = 1,
    ) -> None:
        """
        Lazy collection. Collects and stores submissions, comments and associated users in specified subreddits.

        Args:
            subreddits (List[str]): A list of subreddit names to collect comments from.
            sort_types (List[str]): A list of sorting types for submissions (e.g., 'hot', 'new', 'rising', 'top', 'controversial').
            limit (int, optional): The maximum number of submissions to collect comments from (for each subreddit). Defaults to 10. Set to None to fetch maximum number of submissions.
            level (int, optional): The depth to which comment replies should be fetched. Defaults to 1. Set to None to fetch all comment replies.

        Returns:
            None. Prints the count of collected submissions, comments and user data to the console.
        """

        with console.status(
            "[bold green]Collecting submissions, comments and users from subreddit(s)...",
            spinner="aesthetic",
        ):
            total_submission_inserted_count = 0
            total_comment_inserted_count = 0
            total_redditor_inserted_count = 0

            for subreddit in subreddits:
                logger.info(f"Processing subreddit: {subreddit}")
                for sort_type in sort_types:
                    logger.info(f"Sort type: {sort_type}")
                    r_ = self.reddit.subreddit(subreddit)
                    for submission in getattr(r_, sort_type)(limit=limit):
                        try:
                            # Collect Submission
                            (
                                submission_id,
                                submission_inserted,
                                submission_redditor_inserted,
                            ) = self.submission_data(
                                submission=submission
                            )

                            if submission_inserted is True:
                                total_submission_inserted_count += 1
                            if submission_redditor_inserted is True:
                                total_redditor_inserted_count += 1

                            # Check if comments of submission were crawled
                            link_id_filter = (
                                self.comment_db.select("link_id")
                                .eq("link_id", submission_id)
                                .execute()
                                .dict()["data"]
                            )

                            if len(link_id_filter) >= 1:
                                console.log(
                                    "Submission Link [bold red]{}[/] already in DB-{}".format(
                                        submission_id, self.comment_saver.collection_name
                                    )
                                )

                            else:
                                submission.comments.replace_more(limit=level)
                                # len(submission.comments.list()) would often give different values to submission.num_comments
                                comments = submission.comments.list()
                                (
                                    comment_inserted_count,
                                    comment_redditor_inserted_count,
                                ) = self.comment_data(
                                    comments=comments
                                )
                                total_comment_inserted_count += comment_inserted_count
                                total_redditor_inserted_count += (
                                    comment_redditor_inserted_count
                                )

                        except Exception as error:
                            logger.error(f"Error processing submission {submission.id}: {error}")
                            console.print_exception()
                            console.save_html(
                                os.path.join(
                                    self.error_log_path, f"t3_{submission.id}.html"
                                )
                            )
                            continue

        return logger.info(
            f"{total_submission_inserted_count} submissions, {total_comment_inserted_count} comments, and {total_redditor_inserted_count} users collected from subreddit(s) {subreddits}"
        )

    def submission_from_user(
        self,
        user_names: List[str],
        sort_types: List[str],
        limit: int = 10,
    ) -> None:
        """
        Collects and stores submissions from specified user(s).

        Args:
            user_names (List[str]): A list of Reddit usernames from which to collect submissions.
            sort_types (List[str]): A list of sorting types for user's submissions (e.g., 'hot', 'new', 'rising', 'top', 'controversial').
            limit (int, optional): The maximum number of submissions to collect for each user. Defaults to 10.

        Returns:
            None. Prints the count of collected submission data to the console.
        """
        with console.status(
            "[bold green]Collecting submissions from specified user(s)...",
            spinner="aesthetic",
        ):
            total_submission_inserted_count = 0
            for user_name in user_names:
                logger.info(f"Processing user: {user_name}")
                redditor = self.reddit.redditor(user_name)
                for sort_type in sort_types:
                    logger.info(f"Sort type: {sort_type}")
                    try:
                        submissions = [
                            submission
                            for submission in getattr(redditor.submissions, sort_type)(
                                limit=limit
                            )
                        ]
                        for submission in submissions:
                            try:
                                (
                                    submission_id,
                                    submission_inserted,
                                ) = self.submission_data(
                                    submission=submission
                                )[
                                    :2
                                ]
                                if submission_inserted is True:
                                    total_submission_inserted_count += (
                                        submission_inserted
                                    )
                            except Exception as error:
                                logger.error(f"Error processing submission {submission_id}: {error}")
                                console.print_exception()
                                console.save_html(
                                    os.path.join(
                                        self.error_log_path, f"t3_{submission_id}.html"
                                    )
                                )
                                continue

                    except Exception as error:
                        logger.error(f"Error processing user {user_name}: {error}")
                        console.print_exception()
                        console.save_html(
                            os.path.join(self.error_log_path, f"user_{user_name}.html")
                        )
                        continue
        return logger.info(
            f"{total_submission_inserted_count} submission data collected from {len(user_names)} user(s)"
        )

    def comment_from_user(
        self,
        user_names: List[str],
        sort_types: List[str],
        limit: int = 10,
    ) -> None:
        """
        Collects and stores comments from specified user(s).

        Args:
            user_names (List[str]): A list of Reddit usernames from which to collect comments. Must to user name, not id.
            sort_types (List[str]): A list of sorting types for user's comments (e.g., 'hot', 'new', 'rising', 'top', 'controversial').
            limit (int, optional): The maximum number of comments to collect for each user. Defaults to 10.

        Returns:
            None. Prints the count of collected comment data to the console.
        """
        with console.status(
            "[bold green]Collecting comments from user(s)...", spinner="aesthetic"
        ):
            total_comment_inserted_count = 0
            for user_name in user_names:
                logger.info(f"Processing user: {user_name}")
                redditor = self.reddit.redditor(user_name)
                for sort_type in sort_types:
                    logger.info(f"Sort type: {sort_type}")
                    try:
                        comments = [
                            comment
                            for comment in getattr(redditor.comments, sort_type)(
                                limit=limit
                            )
                        ]
                        comment_inserted_count = self.comment_data(
                            comments=comments
                        )[0]
                        total_comment_inserted_count += comment_inserted_count
                    except Exception as error:
                        logger.error(f"Error processing user {user_name}: {error}")
                        console.print_exception()
                        console.save_html(
                            os.path.join(self.error_log_path, f"user_{user_name}.html")
                        )
                        continue

        return logger.info(
            f"{total_comment_inserted_count} comment data collected from {len(user_names)} user(s)"
        )

    def submission_by_keyword(
        self, subreddits: List[str], query: str, limit: int = 10
    ) -> None:
        """
        Collects and stores submissions with specified keywords from given subreddits.

        You can customize the search behavior by leveraging boolean operators:
        - AND: Requires all connected words to be present in the search results.
        E.g., 'cats AND dogs' returns results with both "cats" and "dogs."
        - OR: Requires at least one of the connected words to match.
        E.g., 'cats OR dogs' returns results with either "cats" or "dogs."
        - NOT: Excludes results containing specific words.
        E.g., 'cats NOT dogs' returns results with "cats" but without "dogs."
        - Using parentheses ( ) groups parts of a search together.

        Note: Be cautious with multiple boolean operators; use parentheses to specify behavior.

        Args:
            subreddits (List[str]): List of subreddit names to collect submissions from.
            query (str): Search terms.
            limit (int, optional): Maximum number of submissions to collect. Defaults to 10.

        Returns:
            None. Prints the count of collected submissions data to the console.
        """

        with console.status(
            "[bold green]Collecting submissions with specified keyword(s)...",
            spinner="aesthetic",
        ):
            total_submission_inserted_count = 0
            for subreddit in subreddits:
                logger.info(f"Processing subreddit: {subreddit}")
                r_ = self.reddit.subreddit(subreddit)
                for submission in r_.search(query, sort="relevance", limit=limit):
                    try:
                        (
                            submission_id,
                            submission_inserted,
                        ) = self.submission_data(
                            submission=submission,
                            insert_redditor=False,
                        )[:2]

                        if submission_inserted is True:
                            total_submission_inserted_count += 1

                    except Exception as error:
                        logger.error(f"Error processing submission {submission_id}: {error}")
                        console.print_exception()
                        console.save_html(
                            os.path.join(
                                self.error_log_path, f"t3_{submission_id}.html"
                            )
                        )
                        continue

        return logger.info(
            f"{total_submission_inserted_count} submissions collected from subreddit(s) {subreddits} with query='{query}'"
        )

    def comment_from_submission(
        self,
        submission_ids: List[str],
        level: Optional[int] = 1,
    ) -> None:
        """
        Collects and stores comments from specified submission id(s).

        Parameters:
            submission_ids (List[str]): A list of submission IDs from which to collect comments.
            level (Optional[int]): The depth of comments to collect. Defaults to 1.

        Returns:
            None
        """
        with console.status(
            "[bold green]Collecting comments from submission id(s)...",
            spinner="aesthetic",
        ):
            total_comment_inserted_count = 0
            for submission_id in submission_ids:
                logger.info(f"Processing submission: {submission_id}")
                submission = self.reddit.submission(submission_id)
                try:
                    # Check if comments of submission were crawled
                    link_id_filter = (
                        self.comment_db.select("link_id")
                        .eq("link_id", submission_id)
                        .execute()
                        .dict()["data"]
                    )

                    if len(link_id_filter) >= 1:
                        console.log(
                            f"Submission Link [bold red]{submission_id}[/] already in DB-{self.comment_saver.collection_name}"
                        )

                    else:
                        submission.comments.replace_more(limit=level)
                        comments = submission.comments.list()
                        comment_inserted_count = self.comment_data(
                            comments=comments, insert_redditor=False
                        )[0]
                        total_comment_inserted_count += comment_inserted_count
                except Exception as error:
                    logger.error(f"Error processing submission {submission.id}: {error}")
                    console.print_exception()
                    console.save_html(
                        os.path.join(self.error_log_path, f"t3_{submission.id}.html")
                    )
                    continue
        return logger.info(
            f"{total_comment_inserted_count} comments collected from {len(submission_ids)} submission(s)"
        )

    # def user_from_submission(self):
    #     return

    # def user_from_subreddit(self):
    #     return


class update:
    """
    Class to update data from Reddit to Supabase periodically.

    Args:
        reddit_client (praw.Reddit): Reddit client.
        supabase_client (supabase.Client): Supabase client.
        db_config (dict, optional): Database configuration. Defaults to None.
    """

    def __init__(
        self,
        reddit_client: praw.Reddit,
    ) -> None:

        raise ValueError("Invalid input: db_config must be provided.")

        # Get Row Counts for non-archived data
        ## Submission
        self.submission_row_count = (
            self.submission_db.select("archived", count="exact")
            .eq("archived", False)
            .execute()
            .count
        )
        ## Comment
        # For comments, need to access both comment_db and submission_db
        # First, get a list of DISTINCT link_IDs from comment_db
        # Second, check if link_IDs are archived or not from submission_db
        # Third, get a list of non-archived list_IDs
        # Fourth, count number of rows with such a list

        ## User
        # TBD

        # Event to signal the threads to stop
        self.stop_event = Event()

    def submission(self):
        """
        Update submission data from Reddit to Supabase.
        """
        page_size = 1000
        page_numbers = (self.submission_row_count // page_size) + (
            1 if self.submission_row_count % page_size != 0 else 0
        )
        start_row, end_row = 0, min(self.submission_row_count, page_size)

        for page in range(1, page_numbers + 1):
            if page == 1:
                pass
            elif page < (page_numbers - 1):
                start_row += page_size
                end_row += page_size
            else:
                start_row += page_size
                end_row = self.submission_row_count

            columns = set(["submission_id", "score", "upvote_ratio", "num_comments"])
            # Give priority to most recent submissions in the paginated submission
            paginated_submission = (
                self.submission_db.select(*columns)
                .eq("archived", False)
                .order("created_at", desc=True)
                .range(start_row, end_row)
                .execute()
                .model_dump()["data"]
            )

            for submission in track(
                paginated_submission,
                description=f"Updating submission in DB-{self.submission_db_config} {page}\{page_numbers}",
            ):
                submission_id = submission["submission_id"]
                score, upvote_ratio, num_comments = (
                    submission["score"],
                    submission["upvote_ratio"],
                    submission["num_comments"],
                )

                accessed_at = datetime.datetime.utcnow()
                submission = self.reddit.submission(id=submission_id)

                score.update(
                    {accessed_at.isoformat(timespec="seconds"): submission.score}
                )
                upvote_ratio.update(
                    {accessed_at.isoformat(timespec="seconds"): submission.upvote_ratio}
                )
                num_comments.update(
                    {accessed_at.isoformat(timespec="seconds"): submission.num_comments}
                )
                archived = submission.archived
                if archived is True:
                    console.print(f"{submission_id} is archived")

                self.submission_db.update(
                    {
                        "score": score,
                        "upvote_ratio": upvote_ratio,
                        "num_comments": num_comments,
                        "archived": archived,
                    }
                ).eq("submission_id", submission_id).execute()

    def run_task_with_interval(self, task: str, interval: int, duration: int) -> None:
        """
        Run the task with a specified interval and duration.

        Args:
            task (str): Task to perform.
            interval (int): Time interval between tasks in seconds.
            duration (int): Duration for which the task should run in seconds.
        """
        loop_start = time.time()
        loop_end = loop_start + duration if duration else float("inf")
        update_count = 0

        while (
            time.time() < loop_end and not self.stop_event.is_set()
        ):  # Continue looping until the stop event is set
            if task == "submission":
                start = time.time()
                self.submission()
                update_count += 1
                end = time.time()
                difference = int(end - start)
                if (
                    difference >= interval
                ):  # If updating the DB took more time than the update time interval
                    pass
                else:  # If updating the DB took less time than the update time interval
                    console.log(
                        f"[bold green]Updated successfully[/] ({difference} seconds). Commencing next schedule in {interval-difference} seconds"
                    )
                    time.sleep(interval - difference)

            elif task == "comment":
                row_count = None
            elif task == "user":
                row_count = None

        self.stop_event.set()

        return console.print(
            f"[bold green]Processed {update_count} cycles of submission updates, each comprising {self.submission_row_count} submissions."
        )

    def schedule_task(self, task: str, duration: str) -> None:
        """
        Schedule the task with a specified duration and automatically determine the update time interval based on the Row Count.

        Args:
            task (str): Task to perform. Avaliable tasks are 'submission'.
            duration (str): Duration for which the task should run. Options are '1hr', '6hr', '12hr', and '1d'.
        """
        tasks = ["submission", "comment", "user"]
        # Get Row Count
        if task in tasks:
            if task == "submission":
                row_count = self.submission_row_count
            elif task == "comment":
                row_count = None
            elif task == "user":
                row_count = None
        else:
            raise ValueError(
                f"Invalid task type: {task}. Avaliable tasks are 'submission', 'comment', and 'user'."
            )

        # Automatically determine update time interval based on the Row Count
        if row_count <= 1000:
            interval = 10 * 60
        elif row_count > 1000 and row_count <= 3000:
            interval = 30 * 60
        elif row_count > 3000 and row_count <= 6000:
            interval = 60 * 60
        elif row_count > 6000 and row_count <= 36000:
            interval = 6 * 60 * 60
        elif row_count > 36000 and row_count <= 72000:
            interval = 12 * 60 * 60
        elif row_count > 72000:
            interval = 24 * 60 * 60

        duration_in_seconds = {
            "1hr": 60 * 60,
            "6hr": 6 * 60 * 60,
            "12hr": 12 * 60 * 60,
            "1d": 24 * 60 * 60,
        }

        duration_seconds = duration_in_seconds.get(duration)
        if duration_seconds:
            threading.Thread(
                target=self.run_task_with_interval,
                args=(
                    task,
                    interval,
                    duration_seconds,
                ),
                daemon=True,
            ).start()
            while not self.stop_event.is_set():
                time.sleep(0.01)
        else:
            raise ValueError(
                "Invalid duration interval. Avaliable durations are '1hr', '6hr', '12hr', and '1d'."
            )


def get_reddit_client() -> praw.Reddit:
    """
    Connect to the Reddit API using the provided credentials or those stored in the .env file.

    Parameters:
        public_key (str, optional): The public key of your Reddit API application.
        secret_key (str, optional): The secret key of your Reddit API application.
        user_agent (str, optional): The user agent identifying your application.
            A user_agent header is a string of text that is sent with HTTP requests to identify
            the program making the request. It is recommended to use the following format:
            "<Institution>:<ResearchProject> (by /u/YourRedditUserName)".
            For example, "LondonSchoolofEconomics:Govt&Economics (by /u/econ101)"

    Returns:
        praw.Reddit: An instance of the Reddit API client if the connection is successful, else None.
    """

    try:
        reddit_client = praw.Reddit(
            client_id=os.getenv("REDDIT_ID"),
            client_secret=os.getenv("REDDIT_API_KEY"),
            user_agent="CptKrupnik:QSBets (by /u/CptKrupnik)",
        )

        # Currently, there seems to be no method for checking whether API access is authorized
        submission = reddit_client.submission(
            url="https://www.reddit.com/r/reddit/comments/sphocx/test_post_please_ignore/"
        )

        if submission.selftext is not None:
            logger.info("Using existing Reddit credentials.")
            logger.info("Connected to Reddit successfully.")
        return reddit_client

    except Exception as e:
        logger.error(f"Failed to connect to Reddit. Error: {str(e)}")
        return None


def scrape():
    reddit = get_reddit_client()

    collector = collect(reddit_client=reddit)

    subreddits = r_FinInvMarket
    sort_types = ["hot"]

    collector.subreddit_submission_and_comment(
        subreddits=subreddits, sort_types=sort_types, limit=20, level=2
    )

def main():
    logger.info("Available collections: redditor, submission, comment")
    collection = input("Enter collection to query: ").strip()

    logger.info("Provide a basic query as a field and value.")
    value = input("Enter value to match: ").strip()


if __name__ == "__main__":
    load_dotenv(".env")
    # scrape()
    main()
